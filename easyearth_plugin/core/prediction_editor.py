"""
Edit the prediction of a model.
This module provides functionality to edit predictions made by a model, including
adding, updating, and deleting predictions, as well as managing the associated prompts.
"""
from easyearth_plugin.core.utils import setup_logger
import json
from qgis.core import (
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsRectangle,
)
from osgeo import gdal  # GDAL is used for in-memory file operations
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox
import os

# Set up the logger for this module
logger = setup_logger("easyearth_plugin.prediction_editor")

def geojson_to_gpkg(geojson_obj_or_str,
                    gpkg_path,
                    layer_name="prediction_layer",
                    overwrite_layer=True,
                    set_crs_if_missing="EPSG:4326"):
    """
    Convert GeoJSON (str/dict/list) to a GPKG layer and return:
      gpkg_uri ('<gpkg_path>|layername=<layer_name>'), expected_count (int)
    """
    # Normalize input to JSON string
    if isinstance(geojson_obj_or_str, (dict, list)):
        geojson_str = json.dumps(geojson_obj_or_str)
    else:
        geojson_str = str(geojson_obj_or_str)

    # Normalize CRS input (accept QgsCoordinateReferenceSystem or str)
    if hasattr(set_crs_if_missing, "authid"):
        set_crs_if_missing = set_crs_if_missing.authid()

    vsipath = f"/vsimem/{layer_name}.geojson"
    gdal.FileFromMemBuffer(vsipath, geojson_str.encode("utf-8"))

    try:
        vl = QgsVectorLayer(vsipath, layer_name, "ogr")
        if not vl.isValid():
            raise RuntimeError("Failed to parse GeoJSON into a valid layer")

        if not vl.crs().isValid() and set_crs_if_missing:
            vl.setCrs(QgsCoordinateReferenceSystem(set_crs_if_missing))

        expected_count = vl.featureCount()

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = layer_name
        opts.fileEncoding = "UTF-8"
        opts.createOptions = ["SPATIAL_INDEX=YES"]
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteLayer
            if os.path.exists(gpkg_path)
            else QgsVectorFileWriter.CreateOrOverwriteFile
        )

        res = QgsVectorFileWriter.writeAsVectorFormatV3(
            vl, gpkg_path, QgsCoordinateTransformContext(), opts
        )
        # Handle both 2- and 3-tuple returns
        if isinstance(res, tuple):
            err = res[0]
            msg = res[1] if len(res) > 1 else ""
        else:
            err = getattr(res, "error", None)
            msg = getattr(res, "message", "")

        if err != QgsVectorFileWriter.NoError:
            raise RuntimeError(f"GPKG write failed: {msg}")

        gpkg_uri = f"{gpkg_path}|layername={layer_name}"
        return gpkg_uri, expected_count
    finally:
        gdal.Unlink(vsipath)