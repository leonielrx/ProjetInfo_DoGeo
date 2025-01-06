# -*- coding: utf-8 -*-
"""
Created on Mon Dec 16 16:35:11 2024

@author: Léonie Leroux

Fichier de configuration: calcule les emprises des projections dans leur propre
système de coordonnées, et ressortir le tout sous la forme d'un fichier json
"""

# from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
# from qgis.PyQt.QtGui import QIcon
# from qgis.PyQt.QtWidgets import QAction
# from qgis.core import QgsPointXY
# from qgis.core import QgsCoordinateReferenceSystem
# from qgis.core import QgsReferencedPointXY
# from qgis.core import QgsCoordinateTransform
# from qgis.core import QgsProject
# from qgis.core import QgsRectangle
# from qgis.core import QgsCoordinateTransformContext
# from qgis.core import QgsCsException

# # Initialize Qt resources from file resources.py
# from .resources import *

# # Import the code for the DockWidget
# from .IdentifProj_dockwidget import IdentifProjDockWidget
# import os.path
import json
import os
from qgis.core import QgsCoordinateReferenceSystem, QgsProviderRegistry


def calc_BBox():
    
    # Liste pour stocker les informations des CRS
    crs_list = []
    
    # Obtenir tous les CRS dans la base de données QGIS
    crs_database = QgsProviderRegistry.instance().providerMetadata("crs").dataSourceUri()
    crs_ids = QgsCoordinateReferenceSystem.listOfAuthIds()
    
    for auth_id in crs_ids:
        crs = QgsCoordinateReferenceSystem(auth_id)
        if crs.isValid():
            bounds = crs.bounds()  # Bounding box en WGS 84
            if not bounds.isNull():
                crs_info = {
                    "auth_id": crs.authid(),
                    "name": crs.description(),
                    "bounding_box": {
                        "x_min": bounds.xMinimum(),
                        "y_min": bounds.yMinimum(),
                        "x_max": bounds.xMaximum(),
                        "y_max": bounds.yMaximum()
                    }
                }
                crs_list.append(crs_info)
    
    # Exporter en fichier JSON
    output_file = "crs_with_bounds.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(crs_list, f, ensure_ascii=False, indent=4)
    
    print(f"Fichier JSON généré : {output_file}")
    
    # # 1. Créer un fichier JSON
    # # Définir les données à écrire dans le fichier JSON
    # data_to_create = {
    #     "name": "John",
    #     "age": 30,
    #     "city": "New York"
    # }
    
    # # Créer (ou écraser) le fichier JSON
    # with open('data.json', 'w') as file:
    #     json.dump(data_to_create, file, indent=4)  # indent=4 pour un fichier lisible
    
    # print("Fichier JSON créé avec les données initiales.")
    
    # # 2. Modifier (éditer) le fichier JSON
    # # Charger le fichier JSON existant
    # with open('data.json', 'r') as file:
    #     data = json.load(file)
    
    # # Modifier les données
    # data['age'] = 31
    # data['city'] = "Los Angeles"
    
    # # Ajouter une nouvelle clé
    # data['email'] = "john@example.com"
    
    # # Sauvegarder les modifications dans le fichier JSON
    # with open('data.json', 'w') as file:
    #     json.dump(data, file, indent=4)
    
    # print("Fichier JSON modifié avec les nouvelles données.")
    
    
if __name__ == "__main__":
    calc_BBox()


