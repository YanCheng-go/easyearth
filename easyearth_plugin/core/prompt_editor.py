"""Handles prompt drawing, collection, and management (points, boxes, etc.)."""

from qgis.gui import QgsRubberBand
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from qgis.core import QgsUnitTypes
from qgis.gui import QgsMapTool
from itertools import chain
from qgis.core import QgsRectangle, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject

class BoxMapTool(QgsMapTool):
    def __init__(self, canvas, on_box_drawn):
        super().__init__(canvas)
        self.canvas = canvas
        self.on_box_drawn = on_box_drawn
        self.start_point = None
        self.is_dragging = False

        self.temp_rubber_band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.temp_rubber_band.setColor(QColor(0, 255, 0, 100))
        self.temp_rubber_band.setWidth(3)
        self.temp_rubber_band.setBrushStyle(Qt.SolidPattern)

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        if not self.start_point:
            self.start_point = point
            self.temp_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        else:
            points = [
                self.start_point,
                QgsPointXY(point.x(), self.start_point.y()),
                point,
                QgsPointXY(self.start_point.x(), point.y()),
                self.start_point
            ]
            box_geom = QgsGeometry.fromPolygonXY([points])
            self.on_box_drawn(box_geom, self.start_point, point)  # Pass both points
            self.temp_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self.start_point = None

    def canvasMoveEvent(self, event):
        if self.start_point:
            end_point = self.toMapCoordinates(event.pos())
            points = [
                self.start_point,
                QgsPointXY(end_point.x(), self.start_point.y()),
                end_point,
                QgsPointXY(self.start_point.x(), end_point.y()),
                self.start_point
            ]
            self.temp_rubber_band.setToGeometry(QgsGeometry.fromPolygonXY([points]), None)

def create_point_box(point, layer, width=500, height=500):
    """
    Create a box geometry in map units (meters) if CRS exists, otherwise in pixel units.

    Args:
        point (QgsPointXY): Center point (map units if CRS exists).
        layer (QgsMapLayer): Layer to determine if CRS is available.
        width (float): Width of the box in meters if CRS exists, or in pixels if no CRS.
        height (float): Height of the box in meters if CRS exists, or in pixels if no CRS.

    Returns:
        QgsGeometry or tuple: If CRS exists, returns QgsGeometry; else, returns (xmin, ymin, xmax, ymax) pixel box.
    """
    if layer.crs().isValid():
        # The layer has a valid CRS -> create box in map units
        layer_crs = layer.crs()
        if layer_crs.mapUnits() == QgsUnitTypes.DistanceMeters:
            proj_crs = layer_crs
        else:
            # Compute UTM zone for accuracy
            import math
            lon = point.x()
            lat = point.y()
            utm_zone = math.floor((lon + 180) / 6) + 1
            if lat >= 0:
                epsg = 32600 + utm_zone
            else:
                epsg = 32700 + utm_zone
            proj_crs = QgsCoordinateReferenceSystem.fromEpsgId(epsg)

        # Transform point to projected CRS
        transform = QgsCoordinateTransform(layer_crs, proj_crs, QgsProject.instance())
        point_proj = transform.transform(point)

        # Create rectangle
        half_w = width / 2
        half_h = height / 2
        rect = QgsRectangle(
            point_proj.x() - half_w, point_proj.y() - half_h,
            point_proj.x() + half_w, point_proj.y() + half_h
        )

        box_geom = QgsGeometry.fromRect(rect)

        # Transform back to layer CRS if needed
        if proj_crs != layer_crs:
            transform_back = QgsCoordinateTransform(proj_crs, layer_crs, QgsProject.instance())
            box_geom.transform(transform_back)

        return box_geom
    else:
        # No valid CRS -> fallback to pixel-based box
        center_x = int(point.x())
        center_y = int(point.y())
        half_w = width // 2
        half_h = height // 2

        # Compute pixel AOI in image coordinates (y downward)
        xmin = center_x - half_w
        xmax = center_x + half_w
        ymin = center_y - half_h
        ymax = center_y + half_h

        # Create a rectangle in pixel coordinates
        rect = QgsRectangle(xmin, ymin, xmax, ymax)
        # Create a QgsGeometry from the rectangle
        box_geom = QgsGeometry.fromRect(rect)

    return box_geom

def map_id(prompts):
    """Map IDs of predictions to their corresponding prompts.
    Args:
        prompts: List of prompts, each with an 'id' and 'type' field.
    Returns:
        A dictionary mapping prompt IDs to their indices in the reordered list.
    """
    points = [p for p in prompts if p.get('properties', {}).get('type', '').lower() == 'point']
    boxes = [p for p in prompts if p.get('properties', {}).get('type', '').lower() == 'box']
    reordered_prompts = list(chain(points, boxes))
    # create a mapping of prompt IDs to their indices that can be used to find the corresponding prediction IDs)
    id_map = {prompt['properties']['id']: idx for idx, prompt in enumerate(reordered_prompts)}
    return id_map

