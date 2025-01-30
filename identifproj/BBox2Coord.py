# -*- coding: utf-8 -*-
"""
Created on Wed Jan 22 09:49:27 2025

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
from qgis.gui import QgsRubberBand
# from qgis.gui import QgsWkbTypes
from PyQt5.QtGui import QColor

from qgis.PyQt.QtCore import Qt
from qgis._core import Qgis
from PyQt5.QtWidgets import QProgressDialog

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the DockWidget
from .IdentifProj_dockwidget import IdentifProjDockWidget
import os.path
import json
import numpy as np


class BBox2Coord(QgsMapTool):
    """
    Contient les méthodes relatives à la fonctionnalité BBox2Coord
    
    Cette classe hérite de la classe QgsMapTool pour rendre plus facile la gestion des 
    intéractions sur la carte (notmment utiliser des méthodes déjà implémentées)
    """
    
    ### Construction de la classe
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
        self.rubberBand = QgsRubberBand(self.canvas, Qgis.GeometryType.Polygon)
        self.rubberBand.setColor(QColor(255, 0, 0, 100))  # Semi-transparent red
        self.rubberBand.setWidth(2)
        self.start_point = None
        self.end_point = None
        self.is_drawing = False  # État pour savoir si on dessine
        self.dockwidget = dockwidget
        self.data = data
        
    ### Méthodes intermédiaire
    def check_polygon_regions(self, polygon):
        """
        Méthode qui assigne à un polygon une (ou plusieurs) partie du monde dans laquelle il se situe
        (sur le même principe de que la méthode check_crs_bounds dans IdentifProj)
        
        polygon : QgsGeometry
        
        primary_regions: liste de String ; correspond aux regions primaires dans lesquelles se trouvent le polygone
        secondary_regions: liste de String ; aux regions secondaire dans lesquelles se trouvent le polygone
        """
            
        ## Définir les rectangles
        west = QgsRectangle(-180.0, -90.0, -60.0, 90.0)
        mid = QgsRectangle(-60.0, -90.0, 60.0, 90.0)
        east = QgsRectangle(60.0, -90.0, 180.0, 90.0)
        
        north = QgsRectangle(-180.0, 0.0, 180.0, 90.0)
        south = QgsRectangle(-180.0, -90.0, 180.0, 0.0)
    
        primary_regions = []
        secondary_regions = []
    
        ## Vérifier les intersections avec les premières et secondes classes
        if polygon.intersects(west):
            primary_regions.append("West")
            if polygon.intersects(north):
                secondary_regions.append("West North")
            if polygon.intersects(south):
                secondary_regions.append("West South")
        
        if polygon.intersects(mid):
            primary_regions.append("Middle")
            if polygon.intersects(north):
                secondary_regions.append("Middle North")
            if polygon.intersects(south):
                secondary_regions.append("Middle South")
        
        if polygon.intersects(east):
            primary_regions.append("East")
            if polygon.intersects(north):
                secondary_regions.append("East North")
            if polygon.intersects(south):
                secondary_regions.append("East South")
        
        return primary_regions, secondary_regions

    ### Gestion de l'interface graphique et méthode principale     
    def canvasPressEvent(self, event):
        """
        Gestion des clics pour l'affichage de la BBox: la BBox est contruite avec deux clics utilisateur
        qui correspondent à deux coins
        
        Pour créer une BBox, il faut faire deux clic gauches, pour supprimer la BBox, utiliser le clic droit
        
        even : évènement clic
        """
        
        ## Gestion des clics gauche
        if event.button() == Qt.LeftButton:
            if not self.is_drawing:
                ## Premier clic : définir le point de départ
                self.start_point = self.toMapCoordinates(event.pos())
                self.is_drawing = True
                self.rubberBand.reset(Qgis.GeometryType.Polygon)
            else:
                ## Deuxième clic : définir le point de fin
                self.end_point = self.toMapCoordinates(event.pos())
                self.is_drawing = False
                self.finalize_bounding_box()
                
        ## Gestion du clic droit       
        elif event.button() == Qt.RightButton:
            ## Clic droit : réinitialiser la bounding box
            self.reset_bounding_box()
    
    def reset_bounding_box(self):
        """
        Méthode attachée au clic droit qui supprimer la BBox affichée en cours
        """
        
        self.rubberBand.reset(Qgis.GeometryType.Polygon)
        self.start_point = None
        self.end_point = None
        self.is_drawing = False
        print("Bounding box réinitialisée.")

    
    def canvasMoveEvent(self, event):
        """
        Méthode pour l'affichage/pré-visualisation de la BBox lorsque l'utilisateur fait glissé la souris
        
        event : évènement sur la map
        """
        
        if self.is_drawing and self.start_point:
            # Mise à jour dynamique du rectangle pendant le déplacement de la souris
            current_point = self.toMapCoordinates(event.pos())
            self.update_rubber_band(self.start_point, current_point)


    
    def update_rubber_band(self, start_point, end_point):
        """
        Met à jour l'affichage du rectangle.
        Rectangle qui s'affiche en fonction de comment l'utilisateur bouge sa souris
        
        start_point: QgsPointXY
        end_point: QgsPointXY
        """
        
        rect = QgsRectangle(start_point, end_point)
        polygon = QgsGeometry.fromPolygonXY([[QgsPointXY(rect.xMinimum(), rect.yMinimum()),
                                              QgsPointXY(rect.xMinimum(), rect.yMaximum()),
                                              QgsPointXY(rect.xMaximum(), rect.yMaximum()),
                                              QgsPointXY(rect.xMaximum(), rect.yMinimum()),
                                              QgsPointXY(rect.xMinimum(), rect.yMinimum())]])
        self.rubberBand.setToGeometry(polygon, QgsProject.instance().crs())
        
    
    def finalize_bounding_box(self):
        """
        Méthode qui calcul les coordonnées de la BBox finale (lorsque l'utilisateur a fait deux clics gauche)
        """
        
        ## Test si l'utilisateur a bien fait deux clics gauche (les deux coins du rectangle)
        if self.start_point and self.end_point:
            
            ## Pour effacer les résultats de la précédente BBox
            ## outputpoly: tableau d'affichage des coordonnées finales
            self.dockwidget.outputPoly.clear() 
            
            ## Créer un rectangle final basé sur les deux points
            self.update_rubber_band(self.start_point, self.end_point)
            rect = QgsRectangle(self.start_point, self.end_point)
            txt = f"BBox coordinates (in WGS84): {rect}"#".toString()}"
            self.dockwidget.polywgs84.setPlainText(txt)
            
            ## Convertir le rectangle en un polygone + créer un QgsRectangle 
            polygon_points = [
                QgsPointXY(rect.xMinimum(), rect.yMinimum()),  # Bas gauche
                QgsPointXY(rect.xMinimum(), rect.yMaximum()),  # Haut gauche
                QgsPointXY(rect.xMaximum(), rect.yMaximum()),  # Haut droit
                QgsPointXY(rect.xMaximum(), rect.yMinimum()),  # Bas droit
                QgsPointXY(rect.xMinimum(), rect.yMinimum())   # Bas gauche pour fermer le polygone
            ]
            
            poly_rec = QgsRectangle(QgsPointXY(rect.xMinimum(), rect.yMaximum()), QgsPointXY(rect.xMaximum(), rect.yMinimum()))
            
            ## Calculer les milieux des côtés du rectangle: le polygone final n'est pas forcément un rectangle en fonction de la projection
            midpoints = [
                QgsPointXY((rect.xMinimum() + rect.xMaximum()) / 2, rect.yMinimum()),  # Milieu du bas
                QgsPointXY((rect.xMinimum() + rect.xMaximum()) / 2, rect.yMaximum()),  # Milieu du haut
                QgsPointXY(rect.xMinimum(), (rect.yMinimum() + rect.yMaximum()) / 2),  # Milieu de gauche
                QgsPointXY(rect.xMaximum(), (rect.yMinimum() + rect.yMaximum()) / 2),  # Milieu de droite
            ]
            
            ## Ajouter les points médians au polygone (au bon endroit)
            polygon_points.insert(1, midpoints[2])  # Milieu de gauche après le bas gauche
            polygon_points.insert(3, midpoints[3])  # Milieu de droite après le bas droit
            polygon_points.insert(4, midpoints[1])  # Milieu du haut après le haut gauche
            polygon_points.insert(5, midpoints[0])  # Milieu du bas après le haut droit
            
            ## Création et géoréférencement du polygon + détermination de la zone de recherche
            poly_user = QgsGeometry.fromPolygonXY([polygon_points])
            prim, sec = self.check_polygon_regions(poly_user)
            crs_poly = QgsCoordinateReferenceSystem("EPSG:4326")
            
            ## On récupère le json de configuration sous la forme d'un dictionnaire + filtrage en fonction de la zone
            data = self.data
            crs_filtre = [item for item in data if set(sec) & set(item.get("sec region", []))]
            
            ## Créer et configurer la barre de progression
            progress = QProgressDialog("Calcul en cours...", "Annuler", 0, len(crs_filtre), self.iface.mainWindow())
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)
            i = 0
            
            ## on boucle sur la liste des crs filtrée
            for crs in crs_filtre:
                
                ## Vérifier si l'utilisateur a annulé l'opération
                if progress.wasCanceled():
                    break
                ## Mettre à jour la barre de progression
                i+=1
                progress.setValue(i)
                
                epsg = crs["auth_id"]
                crs_newpoly = QgsCoordinateReferenceSystem(epsg)
                bounds = crs_newpoly.bounds()
                
                ## Vérifier si le point est dans les limites + si ce n'est pas un crs ESRI
                if bounds.contains(poly_rec) and not crs_newpoly.authid().startswith("ESRI"):
                
                    context = QgsProject.instance().transformContext()
                    transformer = QgsCoordinateTransform(crs_poly, crs_newpoly, context)
                    
                    new_poly_pt = []
                    for pt in polygon_points:
                    
                        try:
                            ## Essayer de transformer le point
                            new_pt = transformer.transform(pt)
                            new_poly_pt.append(new_pt)
                    
                        except QgsCsException as e:
                            ## Gérer l'erreur de transformation (par exemple, ignorer cette transformation)
                            print(f"Erreur lors de la transformation vers {crs_newpt.authid()}: {e}")
                            pass
                    
                    ## Affichage du polygon sur l'interface résultat
                    polygon = QgsGeometry.fromPolygonXY([new_poly_pt])
                    crs_display = str(crs_newpoly.authid()) 
                    poly_display = str(polygon)  
                    item = QTreeWidgetItem([crs_display, poly_display])
                    self.dockwidget.outputPoly.addTopLevelItem(item)
                    
                    
                else: 
                    pass
                
            ## Fermer la barre de progression
            progress.close()
            
            ## Réinitialiser start_point / end_point pour tracer une autre BBox
            self.start_point = None
            self.end_point = None
            
            print("fin du traitement")
            

    







