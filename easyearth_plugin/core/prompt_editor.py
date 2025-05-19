"""Handles prompt drawing, collection, and management (points, boxes, etc.)."""

from qgis.gui import QgsRubberBand
from qgis.core import QgsWkbTypes, QgsGeometry, QgsPointXY
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from qgis.gui import QgsMapTool

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

