from qgis.PyQt.QtWidgets import (QAction, QDockWidget, QPushButton, QVBoxLayout, 
                                QWidget, QMessageBox, QLabel, QHBoxLayout,
                                QLineEdit, QFileDialog, QComboBox, QGroupBox, QGridLayout, QInputDialog, QProgressBar, QCheckBox, QButtonGroup, QRadioButton, QDialog, QApplication)
from qgis.PyQt.QtCore import Qt, QByteArray, QBuffer, QIODevice, QProcess, QTimer, QProcessEnvironment, QVariant, QSettings
from qgis.PyQt.QtGui import QIcon, QMovie, QColor
from qgis.core import (QgsVectorLayer, QgsFeature, QgsGeometry, QgsPolygon, 
                      QgsPointXY, QgsField, QgsProject, QgsPoint, QgsLineString,
                      QgsWkbTypes, QgsRasterLayer, Qgis, QgsApplication, QgsVectorFileWriter, QgsSymbol, QgsCategorizedSymbolRenderer, 
                      QgsRendererCategory, QgsMarkerSymbol, QgsFillSymbol, QgsCoordinateTransform, QgsSingleSymbolRenderer, QgsFields)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
import os
import requests
import base64
from PIL import Image
import io
import numpy as np
import subprocess
import signal
import time
import logging
import shutil
import tempfile
import sys
import yaml
import json
from datetime import datetime

# Setup logger function stays at module level
def setup_logger():
    """Set up the logger for the plugin"""
    try:
        # Create logs directory if it doesn't exist
        plugin_dir = os.path.dirname(__file__)
        log_dir = os.path.join(plugin_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # Create log file name with timestamp
        log_file = os.path.join(log_dir, f'plugin_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)

        # Get logger
        logger = logging.getLogger('EasyEarth')
        logger.setLevel(logging.DEBUG)

        # Remove any existing handlers
        logger.handlers = []

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        # Log initial message
        logger.info("=== EasyEarth Plugin Started ===")
        logger.info(f"Log file: {log_file}")
        
        return logger

    except Exception as e:
        print(f"Failed to setup logger: {str(e)}")
        return None

# Create global logger instance
logger = setup_logger()

class EasyEarthPlugin:
    def __init__(self, iface):
        self.iface = iface
        
        # Initialize logger
        # Use the global logger
        global logger
        self.logger = logger
        
        if self.logger is None:
            # If global logger failed to initialize, create a basic logger
            self.logger = logging.getLogger('EasyEarth')
            self.logger.addHandler(logging.StreamHandler())
            self.logger.setLevel(logging.DEBUG)
        
        self.logger.info("Initializing EasyEarth Plugin")
        
        self.actions = []
        self.menu = 'EasyEarth'
        self.toolbar = self.iface.addToolBar(u'EasyEarth')
        self.toolbar.setObjectName(u'EasyEarth')
        
        # Initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Docker configuration
        self.project_name = "easyearth_plugin"
        self.service_name = self.get_service_name()
        self.image_name = f"{self.project_name}_{self.service_name}"
        self.sudo_password = None  # Add this to store password temporarily
        
        # Initialize map tools and data
        self.canvas = iface.mapCanvas()
        self.point_tool = None
        self.points = []
        self.rubber_bands = []
        self.docker_process = None
        self.server_process = None
        self.server_port = 3781  # Default port
        self.server_url = f"http://0.0.0.0:{self.server_port}/v1/easyearth"
        self.current_image_path = None
        self.current_embedding_path = None
        self.docker_running = False
        self.server_running = False
        self.action = None
        self.dock_widget = None
        self.rubber_band = None
        self.is_selecting_points = False
        self.point_counter = None
        self.point_layer = None
        self.total_steps = 0
        self.current_step = 0
        self.is_drawing = False
        self.draw_tool = None
        self.temp_rubber_band = None
        self.start_point = None
        self.drawn_features = []
        self.temp_vector_path = os.path.join(tempfile.gettempdir(), 'drawn_features.gpkg')
        self.drawn_layer = None
        self.temp_geojson_path = os.path.join(tempfile.gettempdir(), 'drawn_features.geojson')
        self.feature_count = 0  # For generating unique IDs
        self.temp_prompts_geojson = None
        self.temp_predictions_geojson = None
        self.real_time_prediction = False
        self.prompts_layer = None
        self.predictions_layer = None

        # Initialize map tool
        self.map_tool = QgsMapToolEmitPoint(self.canvas)
        self.map_tool.canvasClicked.connect(self.handle_draw_click)
        
        # Initialize rubber bands
        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.rubber_band.setColor(QColor(255, 0, 0))
        self.rubber_band.setWidth(2)
        
        self.temp_rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self.temp_rubber_band.setColor(QColor(255, 0, 0, 50))
        self.temp_rubber_band.setWidth(2)
        
        self.start_point = None
        self.predictions_geojson = None
        self.predictions_layer = None

        # Initialize data directory
        self.data_dir = self.plugin_dir + '/user'

    def add_action(self, icon_path, text, callback, enabled_flag=True,
                  add_to_menu=True, add_to_toolbar=True, status_tip=None,
                  whats_this=None, parent=None):
        """Add a toolbar icon to the toolbar"""
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI"""
        try:
            self.logger.debug("Starting initGui")
            self.logger.info(f"Plugin directory: {self.plugin_dir}")
            
            self.logger.debug("Starting initGui")
            
            # Set up the icon
            icon_path = os.path.join(self.plugin_dir, 'resources/icons/easyearth.png')
            if not os.path.exists(icon_path):
                self.logger.warning(f"Icon not found at: {icon_path}")
                icon = QIcon()
            else:
                icon = QIcon(icon_path)
            
            # Create action with the icon
            self.action = QAction(icon, 'EasyEarth', self.iface.mainWindow())
            self.action.triggered.connect(self.run)
            self.action.setEnabled(True)
            
            # Add to QGIS interface
            self.iface.addPluginToMenu('EasyEarth', self.action)
            self.iface.addToolBarIcon(self.action)
            
            # Create dock widget
            self.dock_widget = QDockWidget('EasyEarth Plugin', self.iface.mainWindow())
            self.dock_widget.setObjectName('EasyEarthPluginDock')
            
            # Create main widget and layout
            main_widget = QWidget()
            main_layout = QVBoxLayout()

            # 1. Docker Control Group
            docker_group = QGroupBox("Docker Control")
            docker_layout = QVBoxLayout()

            # Docker status and button layout
            status_layout = QHBoxLayout()
            docker_label = QLabel("Docker Status:")
            self.docker_status = QLabel("Stopped")
            self.docker_button = QPushButton("Start Docker")
            self.docker_button.clicked.connect(self.toggle_docker)

            status_layout.addWidget(docker_label)
            status_layout.addWidget(self.docker_status)
            status_layout.addWidget(self.docker_button)

            # Add progress bar and progress status
            self.progress_bar = QProgressBar()
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.hide()
            
            self.progress_status = QLabel()
            self.progress_status.setWordWrap(True)
            self.progress_status.hide()
            
            docker_layout.addLayout(status_layout)
            docker_layout.addWidget(self.progress_bar)
            docker_layout.addWidget(self.progress_status)

            docker_group.setLayout(docker_layout)
            main_layout.addWidget(docker_group)

            # 2. Service Information Group
            service_group = QGroupBox("Service Information")
            service_layout = QVBoxLayout()

            # Server status
            status_layout = QHBoxLayout()
            server_label = QLabel("Server Status:")
            self.server_status = QLabel("Checking...")
            status_layout.addWidget(server_label)
            status_layout.addWidget(self.server_status)
            status_layout.addStretch()
            service_layout.addLayout(status_layout)

            # API Information
            api_layout = QVBoxLayout()
            api_label = QLabel("API Endpoints:")
            api_label.setStyleSheet("font-weight: bold;")
            self.api_info = QLabel(f"Base URL: http://0.0.0.0:{self.server_port}/v1/easyearth\n"
                                  f"Predict: /sam-predict\n"
                                  f"Health: /ping")
            self.api_info.setWordWrap(True)
            api_layout.addWidget(api_label)
            api_layout.addWidget(self.api_info)
            service_layout.addLayout(api_layout)

            service_group.setLayout(service_layout)
            main_layout.addWidget(service_group)

            # 3. Image Source Group
            image_group = QGroupBox("Image Source")
            image_layout = QVBoxLayout()
            
            # Image source selection
            source_layout = QHBoxLayout()
            source_label = QLabel("Source:")
            self.source_combo = QComboBox()
            self.source_combo.addItems(["File", "Layer"])
            self.source_combo.currentTextChanged.connect(self.on_image_source_changed)
            source_layout.addWidget(source_label)
            source_layout.addWidget(self.source_combo)
            image_layout.addLayout(source_layout)
            
            # File input
            file_layout = QHBoxLayout()
            self.image_path = QLineEdit()
            self.image_path.setPlaceholderText("Enter image path or click Browse...")
            self.image_path.returnPressed.connect(self.on_image_path_entered)
            self.browse_button = QPushButton("Browse Image")
            self.browse_button.clicked.connect(self.browse_image)
            file_layout.addWidget(self.image_path)
            file_layout.addWidget(self.browse_button)
            image_layout.addLayout(file_layout)
            
            # Layer selection
            self.layer_combo = QComboBox()
            self.layer_combo.hide()
            image_layout.addWidget(self.layer_combo)

            image_group.setLayout(image_layout)
            main_layout.addWidget(image_group)

            # 4. Embedding Settings Group
            embedding_group = QGroupBox("Embedding Settings")
            embedding_layout = QVBoxLayout()

            # Radio buttons for embedding options
            self.embedding_options = QButtonGroup()
            self.no_embedding_radio = QRadioButton("No embedding file")
            self.load_embedding_radio = QRadioButton("Load existing embedding")
            self.save_embedding_radio = QRadioButton("Save new embedding")
            
            self.embedding_options.addButton(self.no_embedding_radio)
            self.embedding_options.addButton(self.load_embedding_radio)
            self.embedding_options.addButton(self.save_embedding_radio)
            
            # Set default option
            self.no_embedding_radio.setChecked(True)

            # Embedding path selection
            self.embedding_path_layout = QHBoxLayout()
            self.embedding_path_edit = QLineEdit()
            self.embedding_path_edit.setEnabled(False)
            self.embedding_browse_btn = QPushButton("Browse")
            self.embedding_browse_btn.setEnabled(False)
            self.embedding_browse_btn.clicked.connect(self.browse_embedding)
            
            self.embedding_path_layout.addWidget(self.embedding_path_edit)
            self.embedding_path_layout.addWidget(self.embedding_browse_btn)

            # Connect radio buttons to handler
            self.embedding_options.buttonClicked.connect(self.on_embedding_option_changed)

            # Add widgets to embedding layout
            embedding_layout.addWidget(self.no_embedding_radio)
            embedding_layout.addWidget(self.load_embedding_radio)
            embedding_layout.addWidget(self.save_embedding_radio)
            embedding_layout.addLayout(self.embedding_path_layout)

            embedding_group.setLayout(embedding_layout)
            main_layout.addWidget(embedding_group)

            # 5. Drawing and Prediction Settings Group
            settings_group = QGroupBox("Drawing and Prediction Settings")
            settings_layout = QVBoxLayout()

            # Drawing type selection
            type_layout = QHBoxLayout()
            type_label = QLabel("Draw type:")
            self.draw_type_combo = QComboBox()
            self.draw_type_combo.addItems(["Point", "Box", "Text"])
            self.draw_type_combo.setItemData(2, False, Qt.UserRole - 1)  # Disable Text option
            self.draw_type_combo.currentTextChanged.connect(self.on_draw_type_changed)
            type_layout.addWidget(type_label)
            type_layout.addWidget(self.draw_type_combo)
            settings_layout.addLayout(type_layout)

            # Drawing button
            self.draw_button = QPushButton("Start Drawing")
            self.draw_button.setCheckable(True)
            self.draw_button.clicked.connect(self.toggle_drawing)
            self.draw_button.setEnabled(False)  # Enabled after image is loaded
            settings_layout.addWidget(self.draw_button)

            settings_group.setLayout(settings_layout)
            main_layout.addWidget(settings_group)

            # TODO: add functions to allow predicting for multiple prompts...
            # # Prediction Group
            # predict_group = QGroupBox("Prediction")
            # predict_layout = QVBoxLayout()
            # self.predict_button = QPushButton("Get Prediction")
            # self.predict_button.clicked.connect(self.get_prediction)
            # predict_layout.addWidget(self.predict_button)
            # predict_group.setLayout(predict_layout)
            # main_layout.addWidget(predict_group)

            # Set the main layout
            main_widget.setLayout(main_layout)
            self.dock_widget.setWidget(main_widget)
            
            # Add dock widget to QGIS
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)

            # Connect to project layer changes
            QgsProject.instance().layersAdded.connect(self.update_layer_combo)
            QgsProject.instance().layersRemoved.connect(self.update_layer_combo)

            # Connect to QGIS quit signal
            QgsApplication.instance().aboutToQuit.connect(self.cleanup_docker)

            # TODO: add check at the start and disable docker button
            # Start periodic server status check
            self.status_timer = QTimer()
            self.status_timer.timeout.connect(self.check_server_status)
            self.status_timer.start(5000)  # Check every 5 seconds

            self.logger.debug("Finished initGui setup")
        except Exception as e:
            self.logger.error(f"Error in initGui: {str(e)}")
            self.logger.exception("Full traceback:")

    def update_layer_combo(self):
        """Update the layers combo box with current raster layers"""
        try:
            self.layer_combo.clear()
            self.layer_combo.addItem("Select a layer...")
            
            # Add all raster layers to combo
            for layer in QgsProject.instance().mapLayers().values():
                if isinstance(layer, QgsRasterLayer):
                    self.layer_combo.addItem(layer.name(), layer)

            # Connect to layer selection change
            self.layer_combo.currentIndexChanged.connect(self.on_layer_selected)

        except Exception as e:
            self.logger.error(f"Error updating layer combo: {str(e)}")

    def on_image_source_changed(self, text):
        """Handle image source selection change"""
        try:
            if text == "File":
                self.image_path.show()
                self.browse_button.show()
                self.layer_combo.hide()
            else:
                self.image_path.hide()
                self.browse_button.hide()
                self.layer_combo.show()
                self.update_layer_combo()

            # Clear any existing layers
            self.cleanup_previous_session()
            
            # Create new prediction layers if a layer is selected
            if text == "Layer" and self.layer_combo.currentData():
                self.image_path.setText(self.layer_combo.currentData().source())
                self.create_prediction_layers()
            
        except Exception as e:
            self.logger.error(f"Error in image source change: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to change image source: {str(e)}")

    def browse_image(self):
        """Open file dialog for image selection"""
        try:
            # Use data_dir as initial directory if it exists
            initial_dir = self.data_dir if self.data_dir and os.path.exists(self.data_dir) else ""

            file_path, _ = QFileDialog.getOpenFileName(
                self.dock_widget,
                "Select Image File",
                initial_dir,
                "Image Files (*.png *.jpg *.jpeg *.tif *.tiff *.JPG *.JPEG *.PNG *.TIF *.TIFF);;All Files (*.*)"
            )
            
            if file_path:
                # Verify the file is within data_dir
                if not os.path.commonpath([file_path]).startswith(os.path.commonpath([self.data_dir])):
                    QMessageBox.warning(
                        None,
                        "Invalid Location",
                        f"Please select an image from within the data directory:\n{self.data_dir}"
                    )
                    return
                    
                self.image_path.setText(file_path)
                # Load image to canvas
                self.load_image()
            
        except Exception as e:
            self.logger.error(f"Error browsing image: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to browse image: {str(e)}")

    def load_image(self):
        """Load the selected image, create prediction layers, and check for existing embeddings"""
        try:
            # Get the image path
            image_path = self.image_path.text()
            if not image_path:
                return

            # Load the image as a raster layer
            raster_layer = QgsRasterLayer(image_path, "Selected Image")
            if not raster_layer.isValid():
                QMessageBox.warning(None, "Error", "Invalid raster layer")
                return

            # Add raster layer to the project
            QgsProject.instance().addMapLayer(raster_layer)
            
            # Create prediction layers
            self.create_prediction_layers()
            
            # Check for existing embedding
            image_name = os.path.splitext(os.path.basename(image_path))[0]
            embedding_dir = os.path.join(self.data_dir, 'embeddings')
            embedding_path = os.path.join(embedding_dir, f"{image_name}.pt")
            
            if os.path.exists(embedding_path):
                # Found existing embedding
                self.load_embedding_radio.setChecked(True)
                self.embedding_path_edit.setText(embedding_path)
                self.embedding_path_edit.setEnabled(True)
                self.embedding_browse_btn.setEnabled(True)
                
                self.iface.messageBar().pushMessage(
                    "Info", 
                    f"Found existing embedding for {image_name}. Will use cached embedding for predictions.",
                    level=Qgis.Info,
                    duration=5
                )
                self.logger.info(f"Found existing embedding at: {embedding_path}")
            else:
                # No existing embedding
                self.save_embedding_radio.setChecked(True)
                embedding_path = os.path.join(embedding_dir, f"{image_name}.pt")
                self.embedding_path_edit.setText(embedding_path)
                self.embedding_path_edit.setEnabled(True)
                self.embedding_browse_btn.setEnabled(True)
                
                self.iface.messageBar().pushMessage(
                    "Info", 
                    f"No existing embedding found for {image_name}. Will generate and save embedding on first prediction.",
                    level=Qgis.Info,
                    duration=5
                )
                self.logger.info(f"No existing embedding found, will save to: {embedding_path}")
        except Exception as e:
            self.logger.error(f"Error loading image: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to load image: {str(e)}")

    def create_empty_geojson(self, file_path):
        """Create an empty GeoJSON file with project CRS"""
        try:
            # Get project CRS
            project_crs = QgsProject.instance().crs()
            
            # Create GeoJSON structure with CRS information
            empty_geojson = {
                "type": "FeatureCollection",
                "name": os.path.basename(file_path),
                "crs": {
                    "type": "name",
                    "properties": {
                        "name": project_crs.authid()
                    }
                },
                "features": []
            }
            
            # Write to file
            with open(file_path, 'w') as f:
                json.dump(empty_geojson, f)
            
            self.logger.debug(f"Created empty GeoJSON file at: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Error creating empty GeoJSON: {str(e)}")
            raise

    def create_vector_layer(self, geojson_path, layer_name, layer_type):
        """Create and style a vector layer with project CRS"""
        try:
            # Create vector layer with polygon geometry
            layer = QgsVectorLayer(f"Polygon?crs={QgsProject.instance().crs().authid()}", 
                                 layer_name, "memory")
            
            if not layer.isValid():
                raise Exception(f"Failed to create {layer_name} layer")
            
            # Add fields based on layer type
            provider = layer.dataProvider()
            if layer_type == "prompt":
                fields = QgsFields()
                fields.append(QgsField("id", QVariant.Int))
                fields.append(QgsField("type", QVariant.String))
                provider.addAttributes(fields)
            else:  # prediction
                fields = QgsFields()
                fields.append(QgsField("id", QVariant.Int))
                fields.append(QgsField("confidence", QVariant.Double))
                fields.append(QgsField("class", QVariant.String))
                provider.addAttributes(fields)
            
            layer.updateFields()
            
            # Save as GeoJSON
            save_options = QgsVectorFileWriter.SaveVectorOptions()
            save_options.driverName = "GeoJSON"
            save_options.fileEncoding = "UTF-8"
            
            # Write the empty layer to GeoJSON
            writer = QgsVectorFileWriter.writeAsVectorFormat(
                layer,
                geojson_path,
                "UTF-8",
                QgsProject.instance().crs(),
                "GeoJSON",
                layerOptions=['COORDINATE_PRECISION=15']
            )
            
            if writer[0] != QgsVectorFileWriter.NoError:
                raise Exception(f"Failed to write GeoJSON file: {writer[0]}")
            
            # Now create the actual layer from the GeoJSON file
            layer = QgsVectorLayer(geojson_path, layer_name, "ogr")
            if not layer.isValid():
                raise Exception(f"Failed to create valid layer from GeoJSON: {geojson_path}")
            
            # Add to project
            QgsProject.instance().addMapLayer(layer)
            
            # Apply styling
            if layer_type == "prompt":
                self.style_prompts_layer(layer)
            else:
                self.style_predictions_layer(layer)
                
            self.logger.debug(f"Created vector layer: {layer_name} from {geojson_path}")
            return layer
                
        except Exception as e:
            self.logger.error(f"Error creating vector layer: {str(e)}")
            raise

    def style_prompts_layer(self, layer):
        """Style the prompts layer with different symbols for points and boxes"""
        try:
            # Create point symbol
            point_symbol = QgsMarkerSymbol.createSimple({
                'name': 'circle',
                'size': '3',
                'color': '255,0,0,255'  # Red
            })

            # Create box symbol
            box_symbol = QgsFillSymbol.createSimple({
                'color': '255,255,0,50',  # Semi-transparent yellow
                'outline_color': '255,0,0,255',  # Red outline
                'outline_width': '0.8'
            })

            # Create categories
            categories = [
                QgsRendererCategory('Point', point_symbol, 'Point'),
                QgsRendererCategory('Box', box_symbol, 'Box')
            ]

            # Create and apply the renderer
            renderer = QgsCategorizedSymbolRenderer('type', categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

        except Exception as e:
            self.logger.error(f"Error styling prompts layer: {str(e)}")
            # Don't raise the exception - just log it and continue
            # This prevents the 'NoneType' error from stopping the layer creation

    def style_predictions_layer(self, layer):
        """Style the predictions layer"""
        try:
            # Create a fill symbol with semi-transparent fill and solid outline
            symbol = QgsFillSymbol.createSimple({
                'color': '0,255,0,50',  # Semi-transparent green
                'outline_color': '0,255,0,255',  # Solid green outline
                'outline_width': '0.8',
                'outline_style': 'solid',
                'style': 'solid'  # Fill style
            })

            # Create and apply the renderer
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            
            # Set layer transparency
            layer.setOpacity(0.5)  # 50% transparent
            
            layer.triggerRepaint()

        except Exception as e:
            self.logger.error(f"Error styling predictions layer: {str(e)}")

    def clear_points(self):
        """Clear all selected points"""
        self.points = []
        if hasattr(self, 'point_counter'):
            self.point_counter.setText("Points: 0")
        if self.point_layer:
            try:
                # Remove features from the point layer
                self.point_layer.dataProvider().truncate()
                self.point_layer.triggerRepaint()
            except Exception as e:
                self.logger.error(f"Error clearing points: {str(e)}")

    def run(self):
        """Run method that loads and starts the plugin"""
        if self.dock_widget.isVisible():
            self.dock_widget.hide()
        else:
            self.dock_widget.show()

    def unload(self):
        """Cleanup when unloading the plugin"""
        try:
            # Clean up temporary files and layers
            self.cleanup_previous_session()
            
            # Remove the plugin menu item and icon
            if self.toolbar:
                self.toolbar.deleteLater()
            for action in self.actions:
                self.iface.removePluginMenu("Easy Earth", action)
                self.iface.removeToolBarIcon(action)
            
            # Clean up Docker resources
            self.cleanup_docker()
            
            # Clear sudo password
            self.sudo_password = None
            
            # Stop the status check timer
            if hasattr(self, 'status_timer'):
                self.status_timer.stop()
                del self.status_timer
            
            # Clear points
            self.clear_points()
            
            # Remove the plugin UI elements
            if self.dock_widget:
                self.iface.removeDockWidget(self.dock_widget)
            
            # Clean up any other resources
            if hasattr(self, 'point_layer') and self.point_layer:
                QgsProject.instance().removeMapLayer(self.point_layer.id())
            
            # Remove temporary drawn features layer
            if hasattr(self, 'drawn_layer') and self.drawn_layer:
                QgsProject.instance().removeMapLayer(self.drawn_layer.id())
            
            # Remove temporary file
            if os.path.exists(self.temp_geojson_path):
                os.remove(self.temp_geojson_path)
            
            # Remove layers
            if self.prompts_layer:
                QgsProject.instance().removeMapLayer(self.prompts_layer.id())
            if self.predictions_layer:
                QgsProject.instance().removeMapLayer(self.predictions_layer.id())
            
            # Remove temporary files
            for file_path in [self.temp_prompts_geojson, self.temp_predictions_geojson]:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            
            self.logger.debug("Plugin unloaded successfully")
        except Exception as e:
            self.logger.error(f"Error during plugin unload: {str(e)}")
            self.logger.exception("Full traceback:")

    def get_sudo_password(self):
        """Get sudo password if not already stored"""
        if not self.sudo_password:
            password, ok = QInputDialog.getText(None, 
                "Sudo Password Required", 
                "Enter sudo password:",
                QLineEdit.Password)
            if ok and password:
                self.sudo_password = password
                return password
            return None
        return self.sudo_password

    def run_sudo_command(self, cmd):
        """Run a command with sudo"""
        try:
            password = self.get_sudo_password()
            if not password:
                return None
            
            full_cmd = f'echo "{password}" | sudo -S {cmd}'
            return subprocess.run(['bash', '-c', full_cmd], capture_output=True, text=True)
        except Exception as e:
            self.logger.error(f"Error running sudo command: {str(e)}")
            return None

    def get_service_name(self):
        """Get the service name from docker-compose.yml"""
        try:
            compose_path = os.path.join(self.plugin_dir, 'docker-compose.yml')
            with open(compose_path, 'r') as file:
                compose_data = yaml.safe_load(file)
                # Get the first service name from the services dictionary
                service_name = next(iter(compose_data.get('services', {})))
                self.logger.debug(f"Found service name: {service_name}")
                return service_name
        except Exception as e:
            self.logger.error(f"Error getting service name: {str(e)}")
            return "easyearth-server"  # fallback default

    def check_docker_image(self):
        """Check if Docker image exists"""
        try:
            result = self.run_sudo_command(f"docker images {self.image_name}:latest -q")
            return bool(result and result.stdout.strip())
        except Exception as e:
            self.logger.error(f"Error checking Docker image: {str(e)}")
            return False

    def check_docker_running(self):
        """Check if Docker daemon is running"""
        try:
            result = self.run_sudo_command("docker info")
            return bool(result and result.returncode == 0)
        except Exception as e:
            self.logger.error(f"Error checking Docker status: {str(e)}")
            return False
    
    def check_container_running(self):
        """Check if the right container has been started outside QGIS"""
        try:
            # Check if container exists and is running
            cmd = f'echo "{self.sudo_password}" | sudo docker ps --filter "name={self.project_name}" --format "{{{{.Status}}}}"'
            self.logger.debug(f"Checking container status with command: {cmd}")
            
            result = self.run_sudo_command(cmd)
            
            if not result:
                self.logger.error("Command execution returned None")
                self.docker_running = False
                
            if result.returncode != 0:
                self.logger.error(f"Command failed with return code: {result.returncode}")
                self.logger.error(f"Error output: {result.stderr}")
                self.docker_running = False

            container_status = result.stdout.strip()
            self.logger.debug(f"Container status: '{container_status}'")
            
            if container_status and 'Up' in container_status:
                self.logger.info(f"Container is running with status: {container_status}")
                # Update UI and state
                self.docker_running = True
                self.docker_status.setText("Running")
                self.docker_button.setText("Stop Docker")
            else:
                self.logger.info(f"Container is not running. Status: {container_status}")
                self.docker_running = False

        except Exception as e:
            self.logger.error(f"Error checking container status: {str(e)}")
            self.logger.exception("Full traceback:")
            return False
    
    def toggle_docker(self):
        """Toggle Docker container state"""
        try:

            self.check_container_running()
            if not self.docker_running:
                # TODO: need to deal with the case where the docker container is initilized outside qgis, so the docker_running is actually true
                # TODO: need to test the server status right after the docker container is finished starting
                # Initialize_data_directory
                self.data_dir = self.initialize_data_directory() # TODO: put in initialization function of qgis 

                # Verify data directory exists
                if not self.verify_data_directory():
                    return

                # Set environment variables including DATA_DIR
                env = QProcessEnvironment.systemEnvironment()
                if self.data_dir and os.path.exists(self.data_dir):
                    env.insert("DATA_DIR", self.data_dir)
                else:
                    # Use default directory if data_dir is not set
                    default_data_dir = os.path.join(self.plugin_dir, 'user')
                    os.makedirs(default_data_dir, exist_ok=True)
                    self.data_dir = default_data_dir
                    # Give a warning window
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Warning)
                    msg.setText("Data directory not defined or not found. Please move input images to the default directory: " + default_data_dir)
                    msg.setWindowTitle("Data Directory Warning")
                    msg.exec_()
                    env.insert("DATA_DIR", default_data_dir)
                    
                # Check if Docker daemon is running
                if not self.check_docker_running():
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Critical)
                    msg.setText("Docker daemon is not running")
                    msg.setInformativeText("Please start Docker using one of these methods:\n\n"
                                        "1. Start Docker Desktop (if installed)\n\n"
                                        "2. Use command line:\n"
                                        "   systemctl start docker (Linux)\n"
                                        "   open -a Docker (macOS)\n\n"
                                        "After starting Docker, try again.")
                    msg.setWindowTitle("Docker Error")
                    msg.exec_()
                    return
                
                # Get password at the start
                if not self.get_sudo_password():
                    return
                
                # Check if container is already running
                if self.check_container_running():
                    self.logger.info("Container already running, skipping startup")
                    self.iface.messageBar().pushMessage(
                        "Info", 
                        "Container already running and server responding",
                        level=Qgis.Info,
                        duration=3
                    )
                    self.docker_running = True
                    self.docker_status.setText("Running")
                    self.docker_button.setText("Stop Docker")
                    self.progress_status.setText("Docker started successfully")
                
                else:
                    compose_path = os.path.join(self.plugin_dir, 'docker-compose.yml')
                    
                    # Initialize progress tracking
                    self.current_step = 0
                    self.count_docker_steps()
                    self.progress_bar.setValue(0)
                    self.progress_bar.show()
                    self.progress_status.show()
                    
                    self.docker_process = QProcess()
                    self.docker_process.finished.connect(self.on_docker_finished)
                    self.docker_process.errorOccurred.connect(self.on_docker_error)
                    self.docker_process.readyReadStandardError.connect(self.on_docker_stderr)
                    self.docker_process.readyReadStandardOutput.connect(self.on_docker_stdout)
                    
                    self.docker_process.setWorkingDirectory(self.plugin_dir)
                    
                    # Check if we need to build
                    if not self.check_docker_image():
                        cmd = f'echo "{self.sudo_password}" | sudo -S docker-compose -p {self.project_name} -f "{compose_path}" up -d --build'
                        self.progress_status.setText("Building Docker image (this may take a while)...")
                    else:
                        cmd = f'echo "{self.sudo_password}" | sudo -S docker-compose -p {self.project_name} -f "{compose_path}" up -d'
                        self.progress_status.setText("Starting existing Docker container...")
                    
                    self.docker_process.start('bash', ['-c', cmd])
                    self.docker_status.setText("Starting")
                    self.docker_button.setEnabled(False)
                
                self.check_server_status()
                    
            else:
                if not self.get_sudo_password():  # TODO: move to the initalization of QGIS
                    return

                compose_path = os.path.join(self.plugin_dir, 'docker-compose.yml')
                cmd = f'echo "{self.sudo_password}" | sudo -S docker-compose -p {self.project_name} -f "{compose_path}" down'
                
                # Create new QProcess instance for stopping
                self.docker_process = QProcess()
                self.docker_process.finished.connect(self.on_docker_finished)
                self.docker_process.errorOccurred.connect(self.on_docker_error)
                self.docker_process.setWorkingDirectory(os.path.dirname(compose_path))
                
                self.docker_process.start('bash', ['-c', cmd])
                self.docker_status.setText("Stopping")
                self.docker_button.setEnabled(False)
                self.progress_status.setText("Stopping Docker container...")
                self.progress_bar.show()

        except Exception as e:
            self.logger.error(f"Error controlling Docker: {str(e)}")
            QMessageBox.critical(None, "Error", f"Error controlling Docker: {str(e)}")

    def on_docker_stderr(self):
        """Handle Docker process stderr output"""
        error = self.docker_process.readAllStandardError().data().decode()
        self.logger.error(f"Docker error: {error}")
        self._process_docker_output(error)

    def on_docker_stdout(self):
        """Handle Docker process stdout output"""
        output = self.docker_process.readAllStandardOutput().data().decode()
        self.logger.debug(f"Docker output: {output}")
        self._process_docker_output(output)

    def on_docker_finished(self, exit_code, exit_status):
        """Handle Docker process completion"""
        try:
            if exit_code == 0:
                self.progress_bar.setValue(self.total_steps)  # Set to 100%
                if not self.docker_running:
                    self.docker_running = True
                    self.docker_status.setText("Running")
                    self.docker_button.setText("Stop Docker")
                    self.progress_status.setText("Docker started successfully")
                else:
                    self.docker_running = False
                    self.docker_status.setText("Stopped")
                    self.docker_button.setText("Start Docker")
                    self.progress_status.setText("Docker stopped successfully")
                    self.server_status.setText("Not Running")
                    self.server_status.setStyleSheet("color: red;")
            else:
                error_output = self.docker_process.readAllStandardError().data().decode()
                self.logger.error(f"Docker command failed with exit code {exit_code}. Error: {error_output}")
                QMessageBox.critical(None, "Error", 
                    f"Docker command failed with exit code {exit_code}")
                self.docker_status.setText("Error")
                self.progress_status.setText(f"Error: Docker command failed with exit code {exit_code}")
        finally:
            self.docker_button.setEnabled(True)
            QTimer.singleShot(2000, lambda: self.progress_bar.hide())
            QTimer.singleShot(2000, lambda: self.progress_status.hide())

    def on_docker_error(self, error):
        """Handle Docker process errors"""
        error_msg = {
            QProcess.FailedToStart: "Failed to start Docker process",
            QProcess.Crashed: "Docker process crashed",
            QProcess.Timedout: "Docker process timed out",
            QProcess.WriteError: "Write error occurred",
            QProcess.ReadError: "Read error occurred",
            QProcess.UnknownError: "Unknown error occurred"
        }.get(error, "An error occurred")
        
        self.logger.error(f"Docker error: {error_msg}")
        QMessageBox.critical(None, "Error", f"Docker error: {error_msg}")
        self.docker_status.setText("Error")
        self.docker_button.setEnabled(True)

    def toggle_drawing(self, checked):
        """Toggle drawing mode"""
        try:
            self.logger.info(f"Toggle drawing called with checked={checked}")
            
            if checked:
                self.logger.info("Starting new drawing session")

                # Initialize drawing tools
                self.logger.info("Initializing drawing tools")
                if not hasattr(self, 'map_tool'):
                    self.logger.error("map_tool not initialized!")
                    raise Exception("Drawing tool not properly initialized")
                    
                if not hasattr(self, 'canvas'):
                    self.logger.error("canvas not initialized!")
                    raise Exception("Canvas not properly initialized")
                    
                self.canvas.setMapTool(self.map_tool)
                
                # Initialize rubber bands if not already done
                if not hasattr(self, 'rubber_band'):
                    self.logger.info("Creating new rubber band")
                    self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
                    self.rubber_band.setColor(QColor(255, 0, 0))
                    self.rubber_band.setWidth(2)
                
                if not hasattr(self, 'temp_rubber_band'):
                    self.logger.info("Creating temporary rubber band")
                    self.temp_rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
                    self.temp_rubber_band.setColor(QColor(255, 0, 0, 50))
                    self.temp_rubber_band.setWidth(2)

                self.draw_button.setText("Stop Drawing")
                
                self.logger.info("Drawing session started successfully")
                
            else:
                self.logger.info("Stopping drawing session")
                self.canvas.unsetMapTool(self.map_tool)
                self.draw_button.setText("Start Drawing")
                self.logger.info("Drawing session stopped")

        except Exception as e:
            self.logger.error(f"Failed to toggle drawing: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to start drawing: {str(e)}")
            self.draw_button.setChecked(False)

    def cleanup_previous_session(self):
        """Clean up temporary files and layers from previous session"""
        try:
            # Remove existing layers
            if self.prompts_layer and self.prompts_layer.isValid():
                QgsProject.instance().removeMapLayer(self.prompts_layer.id())
            if self.predictions_layer and self.predictions_layer.isValid():
                QgsProject.instance().removeMapLayer(self.predictions_layer.id())

            # Remove existing temporary files
            if self.temp_prompts_geojson and os.path.exists(self.temp_prompts_geojson):
                os.remove(self.temp_prompts_geojson)
            if self.temp_predictions_geojson and os.path.exists(self.temp_predictions_geojson):
                os.remove(self.temp_predictions_geojson)

            # Reset feature count
            self.feature_count = 0
            self.prompt_count = 0
            # Clear any existing rubber bands
            if hasattr(self, 'rubber_band') and self.rubber_band:
                self.rubber_band.reset()
            if hasattr(self, 'temp_rubber_band') and self.temp_rubber_band:
                self.temp_rubber_band.reset()
            
            # Reset start point for box drawing
            self.start_point = None

        except Exception as e:
            self.logger.error(f"Error cleaning up previous session: {str(e)}")
            raise

    def handle_draw_click(self, point, button):
        """Handle canvas clicks for drawing"""
        try:
            if not self.draw_button.isChecked() or button != Qt.LeftButton:
                return

            draw_type = self.draw_type_combo.currentText()
            
            # Get the raster layer
            raster_layer = None
            if self.source_combo.currentText() == "File":
                # Check image path for File source
                if not self.image_path.text():
                    raise ValueError("No image selected")
                # Find the raster layer by name "Selected Image"
                for layer in QgsProject.instance().mapLayers().values():
                    if isinstance(layer, QgsRasterLayer) and layer.name() == "Selected Image":
                        raster_layer = layer
                        break
            else:
                # TODO: debug and test when choosing from opened layers
                # TODO: use current or highlighted layer from layer combo box for Layer source
                # Get layer directly from combo box for Layer source
                raster_layer = self.layer_combo.currentData()

            if not raster_layer:
                raise ValueError("No raster layer found")

            # Get raster dimensions and extent
            extent = raster_layer.extent()
            width = raster_layer.width()
            height = raster_layer.height()

            if draw_type == "Point":
                # Reset rubber band for each new point to prevent line creation
                self.rubber_band.reset(QgsWkbTypes.PointGeometry)
                self.rubber_band.addPoint(point)
                
                # Calculate pixel coordinates
                px = int((point.x() - extent.xMinimum()) * width / extent.width())
                py = int((extent.yMaximum() - point.y()) * height / extent.height())
                
                # Ensure coordinates are within image bounds
                px = max(0, min(px, width - 1))
                py = max(0, min(py, height - 1))

                # Show coordinates in message bar
                self.iface.messageBar().pushMessage(
                    "Point Info", 
                    f"Map coordinates: ({point.x():.2f}, {point.y():.2f})\n"
                    f"Pixel coordinates sent to server: ({px}, {py})",
                    level=Qgis.Info,
                    duration=3
                )
                
                # Create prompt feature
                prompt_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [point.x(), point.y()]
                    },
                    "properties": {
                        "id": self.prompt_count if hasattr(self, 'prompt_count') else 1,
                        "type": "Point",
                        "pixel_x": px,
                        "pixel_y": py
                    }
                }
                
                # Add prompt to layer
                self.add_prompt_to_layer([prompt_feature])
                
                # Increment prompt counter
                self.prompt_count = getattr(self, 'prompt_count', 1) + 1
                
                # Prepare prompt for server
                prompt = [{
                    'type': 'Point',
                    'data': {
                        "points": [[px, py]],
                        "labels": [1]
                    }
                }]
                
                # Get prediction
                self.get_prediction(prompt)
                
            elif draw_type == "Box":
                if not self.start_point:
                    # Start drawing box
                    self.start_point = point
                    self.temp_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
                    self.temp_rubber_band.addPoint(point)
                    
                    # Show start point coordinates
                    self.iface.messageBar().pushMessage(
                        "Box Start Point", 
                        f"Start point - Map: ({point.x():.2f}, {point.y():.2f})",
                        level=Qgis.Info,
                        duration=3
                    )
                else:
                    # TODO: to be verified and updated
                    # Calculate pixel coordinates for start point
                    start_px = int((self.start_point.x() - extent.xMinimum()) * width / extent.width())
                    start_py = int((extent.yMaximum() - self.start_point.y()) * height / extent.height())
                    
                    # Calculate pixel coordinates for end point
                    end_px = int((point.x() - extent.xMinimum()) * width / extent.width())
                    end_py = int((extent.yMaximum() - point.y()) * height / extent.height())
                    
                    # Ensure coordinates are within image bounds
                    start_px = max(0, min(start_px, width - 1))
                    start_py = max(0, min(start_py, height - 1))
                    end_px = max(0, min(end_px, width - 1))
                    end_py = max(0, min(end_py, height - 1))
                    
                    # Show box coordinates
                    self.iface.messageBar().pushMessage(
                        "Box Info", 
                        f"Box coordinates sent to server: [{min(start_px, end_px)}, {min(start_py, end_py)}, "
                        f"{max(start_px, end_px)}, {max(start_py, end_py)}]",
                        level=Qgis.Info,
                        duration=3
                    )
                    
                    # Create box geometry for display
                    box_geom = self.create_box_geometry(self.start_point, point)
                    self.rubber_band.addGeometry(box_geom)
                    
                    # Prepare box prompt
                    prompt = [{
                        'type': 'Box',
                        'data': {
                            "boxes": [[
                                min(start_px, end_px),
                                min(start_py, end_py),
                                max(start_px, end_px),
                                max(start_py, end_py)
                            ]]
                        }
                    }]
                    
                    # Get prediction
                    self.get_prediction(prompt)
                    
                    # Reset for next box
                    self.temp_rubber_band.reset()
                    self.start_point = None

        except Exception as e:
            self.logger.error(f"Error handling draw click: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle drawing: {str(e)}")

    def create_box_geometry(self, start, end):
        """Create a box geometry from two points"""
        points = [
            QgsPointXY(start.x(), start.y()),
            QgsPointXY(end.x(), start.y()),
            QgsPointXY(end.x(), end.y()),
            QgsPointXY(start.x(), end.y()),
            QgsPointXY(start.x(), start.y())
        ]
        return QgsGeometry.fromPolygonXY([points])

    def get_prediction(self, prompts):
        """Get prediction from SAM server and add to predictions layer"""
        try:
            if not self.verify_data_directory():
                return
            
            # First check if server is running
            if not self.server_running:
                raise ConnectionError("Server is not running. Please ensure Docker is started and the server is running.")
            
            # Show loading indicator
            self.iface.messageBar().pushMessage("Info", "Getting prediction...", level=Qgis.Info)
            QApplication.setOverrideCursor(Qt.WaitCursor)

            # Get the image path and convert for container
            image_path = self.image_path.text()
            if not image_path:
                raise ValueError("No image selected")
            if not os.path.exists(image_path):
                raise ValueError(f"Image file not found: {image_path}")

            # Initialize embedding variables
            embedding_path = None
            container_embedding_path = None
            save_embeddings = False

            # Handle embedding settings
            if self.load_embedding_radio.isChecked():
                embedding_path = self.embedding_path_edit.text().strip()
                if not embedding_path:
                    raise ValueError("Please select an embedding file to load")
                if not os.path.exists(embedding_path):
                    raise ValueError(f"Embedding file not found: {embedding_path}")
                
                # Convert embedding path for container
                container_embedding_path = self.get_container_path(embedding_path)
                save_embeddings = False
                # logger.debug(f"Loading embeddings from: {embedding_path} -> {container_embedding_path}")
                
            elif self.save_embedding_radio.isChecked():
                embedding_path = self.embedding_path_edit.text().strip()
                if not embedding_path:
                    raise ValueError("Please specify a path to save the embedding")
                
                # Ensure the directory exists
                embedding_dir = os.path.dirname(embedding_path)
                if not os.path.exists(embedding_dir):
                    os.makedirs(embedding_dir, exist_ok=True)
                
                # Convert embedding path for container
                container_embedding_path = self.get_container_path(embedding_path)
                save_embeddings = True
                # logger.debug(f"Will save embeddings to: {embedding_path} -> {container_embedding_path}")

            # Convert image path for container
            container_image_path = self.get_container_path(image_path)
            if not container_image_path:
                raise ValueError("Image must be within the data directory")

            # Prepare request payload
            payload = {
                "image_path": container_image_path,
                "embedding_path": container_embedding_path,
                "prompts": prompts,
                "save_embeddings": save_embeddings
            }

            # Show payload in message bar
            formatted_payload = (
                f"Sending to server:\n"
                f"- Host image path: {image_path}\n"
                f"- Prompt type: {prompts[0]['type']}\n"
            )
            
            if prompts[0]['type'] == 'Point':
                points = prompts[0]['data']['points']
                formatted_payload += f"- Points: {points}\n"
                formatted_payload += f"- Labels: {prompts[0]['data']['labels']}"
            elif prompts[0]['type'] == 'Box':
                boxes = prompts[0]['data']['boxes']
                formatted_payload += f"- Box coordinates: {boxes}"

            self.iface.messageBar().pushMessage(
                "Server Request", 
                formatted_payload,
                level=Qgis.Info,
                duration=5
            )

            # Send request to SAM server
            try:
                response = requests.post(
                    f"{self.server_url}/sam-predict",
                    json=payload,
                    timeout=60000
                )
                
                self.logger.debug(f"Server response status: {response.status_code}")
                self.logger.debug(f"Server response text: {response.text}")

                if response.status_code == 200:
                    try:
                        response_json = response.json()
                        # self.logger.debug(f"Parsed response JSON: {json.dumps(response_json, indent=2)}")
                        
                        if not response_json:
                            raise ValueError("Empty response from server")
                            
                        if 'features' not in response_json:
                            raise ValueError("Response missing 'features' field")
                            
                        features = response_json['features']
                        if not features:
                            self.iface.messageBar().pushMessage(
                                "Warning", 
                                "No predictions returned from server",
                                level=Qgis.Warning,
                                duration=3
                            )
                            return
                        
                        # Add the predictions to our layer
                        self.add_predictions_to_layer(features)
                        
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON response: {str(e)}")
                        
                else:
                    error_msg = f"Server returned status code {response.status_code}"
                    try:
                        error_json = response.json()
                        if 'message' in error_json:
                            error_msg = error_json['message']
                    except:
                        error_msg = response.text
                    raise ValueError(f"Server error: {error_msg}")

            except requests.exceptions.RequestException as e:
                raise ValueError(f"Request failed: {str(e)}")
                
        except Exception as e:
            self.logger.error(f"Error getting prediction: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to get prediction: {str(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def add_predictions_to_layer(self, features, properties=None):
        """Add or append GeoJSON features to predictions layer"""
        try:
            if not features:
                raise ValueError("No features to add")

            # Check if layer is still valid
            if hasattr(self, 'predictions_layer') and self.predictions_layer and not self.predictions_layer.isValid():
                self.predictions_layer = None
                self.predictions_geojson = None

            # Get the raster layer for coordinate transformation
            raster_layer = None
            if self.source_combo.currentText() == "File":
                for layer in QgsProject.instance().mapLayers().values():
                    if isinstance(layer, QgsRasterLayer) and layer.name() == "Selected Image":
                        raster_layer = layer
                        break
            else:
                raster_layer = self.layer_combo.currentData()

            if not raster_layer:
                raise ValueError("No raster layer found")

            # Get raster extent and dimensions
            extent = raster_layer.extent()
            width = raster_layer.width()
            height = raster_layer.height()

            # Create coordinate transform if needed
            raster_crs = raster_layer.crs()
            project_crs = QgsProject.instance().crs()
            transform = QgsCoordinateTransform(raster_crs, project_crs, QgsProject.instance())

            # Convert features from pixel to map coordinates
            for feature in features:
                geom_json = feature.get('geometry')
                if geom_json and geom_json['type'] == 'Polygon':
                    map_coords = []
                    for ring in geom_json['coordinates']:
                        map_ring = []
                        for pixel_coord in ring:
                            # Convert pixel coordinates to map coordinates
                            map_x = extent.xMinimum() + (pixel_coord[0] * extent.width() / width)
                            map_y = extent.yMaximum() - (pixel_coord[1] * extent.height() / height)
                            point = QgsPointXY(map_x, map_y)
                            
                            # Transform coordinates if needed
                            if raster_crs != project_crs:
                                point = transform.transform(point)
                            
                            map_ring.append(point)
                        map_coords.append(map_ring)
                    
                    # Update geometry with transformed coordinates
                    feature['geometry']['coordinates'] = [[(p.x(), p.y()) for p in ring] for ring in map_coords]

            # If this is the first prediction, initialize everything
            if not hasattr(self, 'predictions_geojson') or self.predictions_geojson is None:
                # Initialize the GeoJSON structure
                # TODO: add properties to the GeoJSON structure
                self.predictions_geojson = {
                    "type": "FeatureCollection",
                    "features": [],
                    "crs": {
                        "type": "name",
                        "properties": {
                            "name": QgsProject.instance().crs().authid()
                        }
                    }
                }

                # Add the new feature with properties
                feature = {
                    "type": "Feature",
                    "properties": {
                        "id": self.feature_count if hasattr(self, 'feature_count') else 1,
                        "scores": features[0].get('properties', {}).get('scores', 0),
                    },
                    "geometry": features[0]['geometry']
                }
                
                # Add feature to the collection
                self.predictions_geojson['features'].append(feature)
                
                # Write initial GeoJSON file
                with open(self.temp_predictions_geojson, 'w') as f:
                    json.dump(self.predictions_geojson, f)
                
                # Verify file contents
                self.logger.debug(f"Written GeoJSON content: {json.dumps(self.predictions_geojson, indent=2)}")

                # Create new layer from this file
                self.predictions_layer = QgsVectorLayer(
                    self.temp_predictions_geojson,
                    "SAM Predictions",
                    "ogr"
                )
                
                if not self.predictions_layer.isValid():
                    raise ValueError("Failed to create valid vector layer")
                
                # Add to project
                QgsProject.instance().addMapLayer(self.predictions_layer)
                
                # Apply styling
                self.style_predictions_layer(self.predictions_layer)
                
                self.logger.debug(f"Initial layer feature count: {self.predictions_layer.featureCount()}")
            else:
                # Append new features to existing GeoJSON
                self.predictions_geojson['features'].extend(features)
                
                # Write updated GeoJSON
                with open(self.temp_predictions_geojson, 'w') as f:
                    json.dump(self.predictions_geojson, f, indent=2)
                
                # Check if layer is still in project
                if self.predictions_layer and QgsProject.instance().mapLayer(self.predictions_layer.id()):
                    self.predictions_layer.dataProvider().reloadData()
                    self.predictions_layer.updateExtents()
                    self.predictions_layer.triggerRepaint()
                else:
                    # Recreate layer if it was removed
                    self.predictions_layer = QgsVectorLayer(
                        self.temp_predictions_geojson,
                        "SAM Predictions",
                        "ogr"
                    )
                    QgsProject.instance().addMapLayer(self.predictions_layer)
                    self.style_predictions_layer(self.predictions_layer)

            # Update canvas
            self.iface.mapCanvas().refresh()

            # Verify feature count
            actual_count = self.predictions_layer.featureCount()
            expected_count = len(self.predictions_geojson['features'])
            self.logger.debug(f"Layer feature count: {actual_count} (added: {expected_count})")

        except Exception as e:
            self.logger.error(f"Error adding predictions: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to add predictions: {str(e)}")

    def load_embedding(self, image_path):
        """Load embedding for an image if it exists"""
        try:
            image_name = os.path.basename(image_path)
            base_name = os.path.splitext(image_name)[0]
            embedding_path = os.path.join(self.data_dir, 'embeddings', f"{base_name}.pt")
            
            if os.path.exists(embedding_path):
                # logger.info(f"Found existing embedding for {image_name}")
                return True
            return False
        except Exception as e:
            # logger.error(f"Error checking embedding: {str(e)}")
            return False

    def clear_embeddings(self):
        """Clear all saved embeddings"""
        try:
            embeddings_dir = os.path.join(self.data_dir, 'embeddings')
            if os.path.exists(embeddings_dir):
                for file in os.listdir(embeddings_dir):
                    if file.endswith('.pt'):
                        os.remove(os.path.join(embeddings_dir, file))
            # logger.info("Cleared all embeddings")
        except Exception as e:
            self.logger.error(f"Error clearing embeddings: {str(e)}")

    def toggle_prediction_mode(self, state):
        """Handle prediction mode change"""
        self.real_time_prediction = bool(state)
        self.predict_button.setEnabled(not self.real_time_prediction)

    def check_docker_compose(self):
        """Check if docker-compose.yml exists"""
        compose_path = os.path.join(self.plugin_dir, 'docker-compose.yml')
        if not os.path.exists(compose_path):
            QMessageBox.critical(None, "Error", 
                f"docker-compose.yml not found at: {compose_path}\n"
                "Please ensure the file exists in the plugin directory.")
            return False
        return True

    def cleanup_tmp_files(self):
        """Clean up temporary files"""
        try:
            tmp_compose_path = '/tmp/docker-compose.yml'
            if os.path.exists(tmp_compose_path):
                os.remove(tmp_compose_path)
        except Exception as e:
            self.logger.error(f"Failed to cleanup temporary files: {str(e)}")

    def count_docker_steps(self):
        """Count the total number of steps in docker-compose and Dockerfile"""
        try:
            # Check if image exists first
            if self.check_docker_image():
                # Fewer steps if just starting existing container
                self.total_steps = 3  # pull if needed, create container, start container
                self.progress_bar.setMaximum(self.total_steps)
                return

            compose_path = os.path.join(self.plugin_dir, 'docker-compose.yml')
            dockerfile_path = os.path.join(self.plugin_dir, 'Dockerfile')
            
            steps = 0
            
            # Count steps in Dockerfile
            if os.path.exists(dockerfile_path):
                with open(dockerfile_path, 'r') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        if line.startswith('RUN pip install'):
                            # Count requirements.txt entries if referenced
                            if 'requirements.txt' in line:
                                req_path = os.path.join(self.plugin_dir, 'requirements.txt')
                                if os.path.exists(req_path):
                                    with open(req_path, 'r') as req_file:
                                        # Count non-empty, non-comment lines in requirements.txt
                                        req_steps = sum(1 for l in req_file if l.strip() and not l.strip().startswith('#'))
                                        steps += req_steps
                            else:
                                # Count individual pip install packages
                                packages = line.count('>=') + line.count('==') + line.count('@')
                                steps += max(packages, 1)
                        elif any(line.startswith(cmd) for cmd in [
                            'FROM', 'COPY', 'ADD', 'RUN', 'ENV', 'WORKDIR',
                            'EXPOSE', 'VOLUME', 'CMD', 'ENTRYPOINT'
                        ]):
                            steps += 1
            
            # Add steps for Docker Compose operations
            steps += 5  # network creation, volume creation, image build, container creation, container start
            
            self.total_steps = max(steps, 1)  # Ensure at least 1 step
            self.progress_bar.setMaximum(self.total_steps)
            self.logger.debug(f"Total build steps: {self.total_steps}")
            
        except Exception as e:
            self.logger.error(f"Error counting docker steps: {str(e)}")
            self.total_steps = 0

    def _process_docker_output(self, output):
        """Process Docker output and update progress"""
        progress_indicators = {
            'Pulling': 1,
            'Pull complete': 1,
            'Downloading': 1,
            'Download complete': 1,
            'Extracting': 1,
            'Extract complete': 1,
            'Building': 1,
            'Step': 1,
            'Running': 1,
            'Creating network': 1,
            'Creating volume': 1,
            'Creating container': 1,
            'Starting container': 1,
            'Collecting': 1,  # For pip install progress
            'Installing collected packages': 1,
            'Successfully installed': 1,
            'Requirement already satisfied': 1
        }

        lines = output.split('\n')
        for line in lines:
            line = line.strip()
            if line:
                # Special handling for pip install progress
                if 'pip install' in line:
                    self.progress_status.setText("Installing dependencies...")
                    self.progress_status.show()
                elif 'Successfully built' in line:
                    self.progress_bar.setValue(self.total_steps)
                    self.progress_status.setText("Build completed successfully")
                    return

                for indicator in progress_indicators:
                    if indicator in line:
                        self.current_step += 1
                        progress = min(self.current_step, self.total_steps)
                        self.progress_bar.setValue(progress)
                        self.progress_status.setText(line)
                        self.progress_status.show()
                        self.logger.debug(f"Docker progress: {line}")
                        break

    def check_server_status(self):
        """Check if the server is running by pinging it"""
        try:
            response = requests.get(f"http://0.0.0.0:{self.server_port}/v1/easyearth/ping", timeout=2)
            if response.status_code == 200:
                self.server_status.setText("Running")
                self.server_status.setStyleSheet("color: green;")
                self.server_running = True

                self.docker_running = True
                self.docker_status.setText("Running")
                self.docker_button.setText("Stop Docker")
            else:
                self.server_status.setText("Error")
                self.server_status.setStyleSheet("color: red;")
                self.server_running = False
        except requests.exceptions.RequestException:
            self.server_status.setText("Not Running")
            self.server_status.setStyleSheet("color: red;")
            self.server_running = False

    def cleanup_docker(self):
        """Clean up Docker resources when unloading plugin"""
        try:
            if self.sudo_password:
                compose_path = os.path.join(self.plugin_dir, 'docker-compose.yml')
                cmd = f'echo "{self.sudo_password}" | sudo -S docker-compose -p {self.project_name} -f "{compose_path}" down'
                subprocess.run(['bash', '-c', cmd], check=True)
        except Exception as e:
            self.logger.error(f"Error cleaning up Docker: {str(e)}")

    def on_embedding_option_changed(self, button):
        """Handle embedding option changes"""
        try:
            self.logger.debug(f"Embedding option changed to: {button.text()}")
            enable_path = button != self.no_embedding_radio
            self.embedding_path_edit.setEnabled(enable_path)
            self.embedding_browse_btn.setEnabled(enable_path)
            
            if not enable_path:
                self.embedding_path_edit.clear()
                self.logger.debug("Cleared embedding path")
            
            self.logger.debug(f"Path input enabled: {enable_path}")
        except Exception as e:
            self.logger.error(f"Error in embedding option change: {str(e)}")

    def browse_embedding(self):
        """Browse for embedding file"""
        try:
            if self.load_embedding_radio.isChecked():
                # Browse for existing file
                file_path, _ = QFileDialog.getOpenFileName(
                    None,
                    "Select Embedding File",
                    "",
                    "Embedding Files (*.pt);;All Files (*.*)"
                )
                self.logger.debug(f"Selected existing embedding file: {file_path}")
            else:
                # Browse for save location
                file_path, _ = QFileDialog.getSaveFileName(
                    None,
                    "Save Embedding As",
                    "",
                    "Embedding Files (*.pt);;All Files (*.*)"
                )
                self.logger.debug(f"Selected save location for embedding: {file_path}")

            if file_path:
                self.embedding_path_edit.setText(file_path)
                self.logger.debug(f"Set embedding path to: {file_path}")

        except Exception as e:
            self.logger.error(f"Error browsing embedding: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to browse embedding: {str(e)}")

    def style_drawn_features(self):
        """Apply styling to the drawn features layer"""
        if not self.drawn_layer:
            return

        # Create symbol for points
        point_symbol = QgsMarkerSymbol.createSimple({
            'name': 'circle',
            'color': 'red',
            'size': '4',
        })

        # Create symbol for polygons (boxes)
        polygon_symbol = QgsFillSymbol.createSimple({
            'color': 'rgba(255, 0, 0, 50)',
            'outline_color': 'red',
            'outline_width': '1',
        })

        # Create categories
        categories = [
            QgsRendererCategory('Point', point_symbol, 'Point'),
            QgsRendererCategory('Box', polygon_symbol, 'Box')
        ]

        # Create and apply the renderer
        renderer = QgsCategorizedSymbolRenderer('type', categories)
        self.drawn_layer.setRenderer(renderer)

        # Refresh the layer
        self.drawn_layer.triggerRepaint()

    def on_draw_type_changed(self, draw_type):
        """Handle draw type change"""
        try:
            self.logger.debug(f"Draw type changed to: {draw_type}")
            if self.draw_button.isChecked():
                # If currently drawing, restart with new type
                self.draw_button.setChecked(False)
                self.toggle_drawing(True)
        except Exception as e:
            self.logger.error(f"Error in draw type change: {str(e)}")

    def initialize_data_directory(self):
        """Initialize or load data directory configuration"""
        try:
            settings = QSettings()
            data_dir = settings.value("easyearth/data_dir")
            default_data_dir = os.path.join(self.plugin_dir, 'user')
            
            # Create custom dialog for directory choice
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("Data Directory Configuration")
            msg.setInformativeText(
                "Would you like to:\n\n"
                "1. Use a custom directory for your data\n"
                "2. Use the default directory\n\n"
                f"Default directory: {default_data_dir}"
            )
            custom_button = msg.addButton("Select Custom Directory", QMessageBox.ActionRole)
            default_button = msg.addButton("Use Default Directory", QMessageBox.ActionRole)
            msg.setDefaultButton(custom_button)
            
            msg.exec_()
            clicked_button = msg.clickedButton()
            
            if clicked_button == custom_button:
                # User wants to select custom directory
                data_dir = QFileDialog.getExistingDirectory(
                    self.iface.mainWindow(),
                    "Select Data Directory",
                    os.path.expanduser("~"),
                    QFileDialog.ShowDirsOnly
                )
                
                if not data_dir:  # User cancelled selection
                    self.logger.info("User cancelled custom directory selection, using default")
                    data_dir = default_data_dir
            else:
                # User chose default directory
                data_dir = default_data_dir
            
            # Create the directory and subdirectories
            try:
                os.makedirs(data_dir, exist_ok=True)
                os.makedirs(os.path.join(data_dir, 'embeddings'), exist_ok=True)
                
                # Save the setting
                settings.setValue("easyearth/data_dir", data_dir)
                self.data_dir = data_dir
                
                # Show confirmation
                QMessageBox.information(
                    None,
                    "Data Directory Set",
                    f"Data directory has been set to:\n{data_dir}\n\n"
                    "Please make sure to:\n"
                    "1. Place your input images in this directory\n"
                    "2. Ensure Docker has access to this location"
                )
                
                self.logger.info(f"Data directory set to: {data_dir}")
                
            except Exception as e:
                self.logger.error(f"Error creating directories: {str(e)}")
                QMessageBox.critical(
                    None,
                    "Error",
                    f"Failed to create data directory structure: {str(e)}\n"
                    "Please check permissions and try again."
                )
                return None
            
            return data_dir

        except Exception as e:
            self.logger.error(f"Error initializing data directory: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", 
                f"Failed to initialize data directory: {str(e)}")
            return None

    def get_container_path(self, host_path):
        """Convert host path to container path"""
        if not host_path:
            return None
        
        # Convert path if it's in the data directory
        if host_path.startswith(self.data_dir):
            relative_path = os.path.relpath(host_path, self.data_dir)
            return os.path.join('/usr/src/app/user', relative_path)
        return host_path

    def create_prediction_layers(self):
        """Prepare for prediction and prompt layers"""
        try:
            # Clean up existing layers first
            if hasattr(self, 'prompts_layer') and self.prompts_layer:
                QgsProject.instance().removeMapLayer(self.prompts_layer)
                self.prompts_layer = None
            if hasattr(self, 'predictions_layer') and self.predictions_layer:
                QgsProject.instance().removeMapLayer(self.predictions_layer)
                self.predictions_layer = None
            
            # Reset the GeoJSON data
            self.prompts_geojson = None
            self.predictions_geojson = None
            
            # Create temporary file paths
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_prompts_geojson = os.path.join(
                tempfile.gettempdir(), 
                f'prompts_{timestamp}.geojson'
            )
            self.temp_predictions_geojson = os.path.join(
                tempfile.gettempdir(), 
                f'predictions_{timestamp}.geojson'
            )

            # Initialize feature counter
            self.feature_count = 1
            
            # Initialize prompt counter
            self.prompt_count = 1
            
            self.logger.info(f"Prepared file paths: \n"
                           f"Prompts: {self.temp_prompts_geojson}\n"
                           f"Predictions: {self.temp_predictions_geojson}")

            # Enable drawing controls
            self.draw_button.setEnabled(True)
            
            self.iface.messageBar().pushMessage(
                "Success", 
                "Ready for drawing prompts and predictions",
                level=Qgis.Success,
                duration=3
            )

        except Exception as e:
            self.logger.error(f"Error preparing layers: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to prepare layers: {str(e)}")

    def on_layer_selected(self, index):
        """Handle layer selection change and check for existing embeddings"""
        try:
            if index > 0:  # Skip "Select a layer..." item
                selected_layer = self.layer_combo.currentData()
                if not selected_layer:
                    return
                
                self.image_path.setText(selected_layer.source())

                # Create prediction layers
                self.create_prediction_layers()
                
                # Check for existing embedding
                layer_source = selected_layer.source()
                image_name = os.path.splitext(os.path.basename(layer_source))[0]
                embedding_dir = os.path.join(self.data_dir, 'embeddings')
                embedding_path = os.path.join(embedding_dir, f"{image_name}.pt")
                
                if os.path.exists(embedding_path):
                    # Found existing embedding
                    self.load_embedding_radio.setChecked(True)
                    self.embedding_path_edit.setText(embedding_path)
                    self.embedding_path_edit.setEnabled(True)
                    self.embedding_browse_btn.setEnabled(True)
                    
                    self.iface.messageBar().pushMessage(
                        "Info", 
                        f"Found existing embedding for {image_name}. Will use cached embedding for predictions.",
                        level=Qgis.Info,
                        duration=5
                    )
                    self.logger.info(f"Found existing embedding at: {embedding_path}")
                else:
                    # No existing embedding
                    self.save_embedding_radio.setChecked(True)
                    embedding_path = os.path.join(embedding_dir, f"{image_name}.pt")
                    self.embedding_path_edit.setText(embedding_path)
                    self.embedding_path_edit.setEnabled(True)
                    self.embedding_browse_btn.setEnabled(True)
                    
                    self.iface.messageBar().pushMessage(
                        "Info", 
                        f"No existing embedding found for {image_name}. Will generate and save embedding on first prediction.",
                        level=Qgis.Info,
                        duration=5
                    )
                    self.logger.info(f"No existing embedding found, will save to: {embedding_path}")

        except Exception as e:
            self.logger.error(f"Error handling layer selection: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle layer selection: {str(e)}")

    def on_image_path_entered(self):
        """Handle manual entry of image path"""
        try:
            image_path = self.image_path.text().strip()
            if not image_path:
                return

            # Check if file exists
            if not os.path.exists(image_path):
                QMessageBox.warning(None, "Error", f"Image file not found: {image_path}")
                return

            # Check if it's an image file
            valid_extensions = ['.png', '.jpg', '.jpeg', '.tif', '.tiff']
            # extend with capitalize
            valid_extensions.extend([ext.upper() for ext in valid_extensions])

            if not any(image_path.lower().endswith(ext) for ext in valid_extensions):
                QMessageBox.warning(None, "Error", 
                    "Invalid file type. Please select an image file (PNG, JPG, TIFF)")
                return

            # Load the image and check for embeddings
            self.load_image()

        except Exception as e:
            self.logger.error(f"Error processing entered image path: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to load image: {str(e)}")

    def verify_data_directory(self):
        """Verify data directory is properly set up"""
        if not self.data_dir:
            QMessageBox.critical(None, "Error", 
                "Data directory not configured.\n"
                "Please restart the plugin to configure the data directory.")
            return False
        
        if not os.path.exists(self.data_dir):
            QMessageBox.critical(None, "Error", 
                f"Data directory not found: {self.data_dir}\n"
                "Please restart the plugin to reconfigure the data directory.")
            return False
        
        return True

    def add_prompt_to_layer(self, features):
        """Add or append prompt features to prompts layer"""
        try:
            if not features:
                raise ValueError("No features to add")

            self.logger.debug(f"Incoming prompt features: {json.dumps(features, indent=2)}")

            # If this is the first prompt, initialize everything
            if not hasattr(self, 'prompts_geojson') or self.prompts_geojson is None:
                # Initialize the GeoJSON structure
                self.prompts_geojson = {
                    "type": "FeatureCollection",
                    "crs": {
                        "type": "name",
                        "properties": {
                            "name": QgsProject.instance().crs().authid()
                        }
                    },
                    "features": []  # Start with empty features list
                }
                
                # Add the new features
                self.prompts_geojson['features'] = features
                
                # Write initial GeoJSON file
                with open(self.temp_prompts_geojson, 'w') as f:
                    json.dump(self.prompts_geojson, f)
                
                # Verify file contents
                self.logger.debug(f"Written GeoJSON content: {json.dumps(self.prompts_geojson, indent=2)}")
                
                # Create new layer from this file
                self.prompts_layer = QgsVectorLayer(
                    self.temp_prompts_geojson,
                    "Drawing Prompts",
                    "ogr"
                )
                
                if not self.prompts_layer.isValid():
                    raise ValueError("Failed to create valid vector layer")
                
                # Add to project
                QgsProject.instance().addMapLayer(self.prompts_layer)
                
                # Apply styling
                self.style_prompts_layer(self.prompts_layer)
                
                self.logger.debug(f"Initial layer feature count: {self.prompts_layer.featureCount()}")
                
            else:
                # Append new features to existing GeoJSON
                self.prompts_geojson['features'].extend(features)
                
                # Write updated GeoJSON
                with open(self.temp_prompts_geojson, 'w') as f:
                    json.dump(self.prompts_geojson, f)
                
                # Verify file contents
                self.logger.debug(f"Updated GeoJSON content: {json.dumps(self.prompts_geojson, indent=2)}")
                
                # Reload the layer
                self.prompts_layer.dataProvider().reloadData()
                self.prompts_layer.updateExtents()
                self.prompts_layer.triggerRepaint()

            # Update canvas
            self.iface.mapCanvas().refresh()

            # Verify feature count
            actual_count = self.prompts_layer.featureCount()
            expected_count = len(self.prompts_geojson['features'])
            self.logger.debug(f"Layer feature count: {actual_count} (added: {expected_count})")

        except Exception as e:
            self.logger.error(f"Error adding prompts: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to add prompts: {str(e)}")
