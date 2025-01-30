# -*- coding: utf-8 -*-
"""
Created on Mon Jan 13 09:28:30 2025

@author: Formation
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsPointXY
from qgis.core import QgsCoordinateReferenceSystem
from qgis.core import QgsReferencedPointXY
from qgis.core import QgsCoordinateTransform
from qgis.core import QgsProject
from qgis.core import QgsRectangle
from qgis.core import QgsCoordinateTransformContext
from qgis.core import QgsCsException
from qgis.core import QgsCoordinateReferenceSystem, QgsProviderRegistry
from qgis.core import QgsGeometry
from qgis.core import QgsRasterLayer
from qgis.core import QgsVectorLayer
from qgis.core import QgsField
from qgis.core import QgsFeature
from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QMainWindow

from qgis.gui import QgsMapTool
from qgis.PyQt.QtCore import Qt
from qgis._core import Qgis
from PyQt5.QtWidgets import QProgressDialog

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .IdentifProj_dockwidget import IdentifProjDockWidget
import os.path
import json


class Point2Coord(QgsMapTool):
    """
    Contient les méthodes relatives à la fonctionnalité Point2Coord
    
    Cette classe hérite de la classe QgsMapTool pour rendre plus facile la gestion des 
    intéractions sur la carte (notmment utiliser des méthodes déjà implémentées)
    """
    
    def __init__(self, iface, dockwidget, data):
        """
        Constructeur

        iface: QgsInterface; interface du plugin (qui est la même pour toutes les classes)
        dockwidget : Composante graphique de l'interface 
        data : liste de dictonnaire ; correspond au json de configuration chargé dans IdentifProj
        """
        self.iface = iface
        super().__init__(iface.mapCanvas())
        self.canvas = iface.mapCanvas()
        self.p2c_isActive = True
        self.dockwidget = dockwidget
        self.data = data
        
    
    def classif_pt(self, point):
        """
        Méthode qui assigne à un point une partie du monde dans laquelle ce point se situe
        (sur le même principe de que la méthode check_crs_bounds dans IdentifProj)
        
        point : QgsPointXY
        
        primary_region: liste de String ; correspond à la première zone dans laquelle se trouve le point
        sec_region: liste de String ; correspond à la seconde zone dans laquelle se trouve le point
        """
        
        # Définir les rectangles
        west = QgsRectangle(-180.0, -90.0, -60.0, 90.0)
        mid = QgsRectangle(-60.0, -90.0, 60.0, 90.0)
        east = QgsRectangle(60.0, -90.0, 180.0, 90.0)
        
        north = QgsRectangle(-180.0, 0.0, 180.0, 90.0)
        south = QgsRectangle(-180.0, -90.0, 180.0, 0.0)
    
        primary_region = ""
        sec_region = ""
    
        # Vérifier dans quelle région primaire se trouve le point
        if west.contains(point):
            primary_region = "West"
        elif mid.contains(point):
            primary_region = "Middle"
        elif east.contains(point):
            primary_region = "East"
    
        # Vérifier la région secondaire (Nord ou Sud)
        if north.contains(point):
            sec_region = primary_region + " North"
        elif south.contains(point):
            sec_region = primary_region + " South"
    
        return primary_region, sec_region

        
    def canvasPressEvent(self, event):
        """
        Méthode qui détecte un clic sur la carte, affiche les coordonnées et transforme les coordonnées cliquées dans les 
        différentes projections (+ affichage des résultats dans l'interface)
        
        event: évènement à venir détecter (le clic sur la carte)
        """
        
        ## Définition du crs de la carte (reste la même pendant tout le projet)
        crs_map = QgsCoordinateReferenceSystem("EPSG:4326")
        
        ## Pour effacer les résultats du précédent point
        ## "outputFrame" est le tableau de résultat des coordonnées transformées
        self.dockwidget.outputFrame.clear() 
        
        ## Test si la fonctionnalité est activée
        if self.p2c_isActive == True:
            
            ## Récupération des coordonnées du point cliqué + affichage de ses coordonnées
            point = self.toMapCoordinates(event.pos())
            pt = QgsReferencedPointXY(point, crs_map)
            coords_text = f"Coordinates of the point (in WGS84) : X = {point.x()}, Y = {point.y()} "
            self.dockwidget.outputPT.setPlainText(coords_text)
                
            ## On classe le point en fonction de sa zone primaire et secondaire
            crs_point = pt.crs()
            prim, sec = self.classif_pt(pt)
            
            ## Récupération des données de configuration sous la forme d'un dictionnaire
            data = self.data
            
            ## On filtre les SRC disponibles pour ne cibler que les SRC valides dans la zone du point (gain de temps)
            crs_filtre = [item for item in data if sec in item.get("sec region", [])]
            
            ## Créer et configurer la barre de progression
            progress = QProgressDialog("Calcul en cours...", "Annuler", 0, len(crs_filtre), self.iface.mainWindow())
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            i = 0
            
            ## bouclesur le SRC filtrés
            for crs in crs_filtre:
                
                ## Vérifier si l'utilisateur a annulé l'opération
                if progress.wasCanceled():
                    break
                
                ## Mettre à jour la barre de progression
                i+=1
                progress.setValue(i)
                
                ## Récupération des attributs du SRC  
                epsg = crs["auth_id"]
                crs_newpt = QgsCoordinateReferenceSystem(epsg)
                bounds = crs_newpt.bounds()
                
                ## Vérifier si le point est dans les limites de la projection + si ce n'est pas un SRC ESRI
                if bounds.contains(pt) and not crs_newpt.authid().startswith("ESRI"):
                
                    context = QgsProject.instance().transformContext()
                    transformer = QgsCoordinateTransform(crs_point, crs_newpt, context)
                    
                    try:
                        ## Essayer de transformer le point
                        newpt = transformer.transform(pt)
                        newpt = QgsReferencedPointXY(newpt, crs_newpt)
                        
                        ## Ajouter les coordonnées transformées à l'interface
                        crs_display = str(newpt.crs().authid())
                        x = f"{newpt.x():.4f}"
                        y = f"{newpt.y():.4f}"
                        item = QTreeWidgetItem([crs_display, x, y])
                        self.dockwidget.outputFrame.addTopLevelItem(item)
                
                    except QgsCsException as e:
                        ## Gérer l'erreur de transformation (par exemple, ignorer cette transformation)
                        print(f"Erreur lors de la transformation vers {crs_newpt.authid()}: {e}")
                        pass
                    
                    
                else: 
                    pass
                
            ## Fermer la barre de progression
            progress.close()
                
                
            
            
            
            
            
            
            