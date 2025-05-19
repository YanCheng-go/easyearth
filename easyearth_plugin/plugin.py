# TODO: split into multiple files, plugin.py, docker_manager.py, ui.py, layer_manager.py, prediction.py, utils.py
# TODO: allow scrapping from wms file...
# TODO: add function for converting local models to hugging face models

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

from .core.utils import setup_logger
from .core.prompt_editor import BoxMapTool


class EasyEarthPlugin:
    def __init__(self, iface):
        self.iface = iface

        # Initialize logger
        self.logger = setup_logger()

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
        self.last_pred_time = 0  # timestamp when the real-time prediction is unchecked. or the last batch prediction was done
        self.prompts_layer = None
        self.predictions_layer = None

        # Initialize map tool
        self.map_tool = QgsMapToolEmitPoint(self.canvas)
        self.map_tool.canvasClicked.connect(self.handle_draw_click)

        # Initialize tool for drawing boxes
        self.box_tool = BoxMapTool(self.canvas, self.on_box_drawn)

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
        self.tmp_dir = os.path.join(self.plugin_dir, 'tmp')

        self.model_path = None

        # initialize image crs and extent...
        self.raster_crs = None
        self.raster_extent = None
        self.raster_width = None
        self.raster_height = None

        self.project_crs = QgsProject.instance().crs()
        QgsProject.instance().crsChanged.connect(self.on_project_crs_changed)

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
                                  f"Infer with point or box prompts: /sam-predict\n"
                                  f"Infer with no prompts: /segment-predict\n"
                                  f"Health check: /ping")
            self.api_info.setWordWrap(True)
            api_layout.addWidget(api_label)
            api_layout.addWidget(self.api_info)
            service_layout.addLayout(api_layout)

            service_group.setLayout(service_layout)
            main_layout.addWidget(service_group)

            # Model Selection Group
            model_group = QGroupBox("Segmentation Model")
            model_layout = QHBoxLayout()

            self.model_combo = QComboBox()
            self.model_combo.setEditable(True)
            # Add common models
            # TODO: add and test model models
            self.model_combo.addItems([
                "facebook/sam-vit-base",
                "facebook/sam-vit-large",
                "facebook/sam-vit-huge",
                "restor/tcd-segformer-mit-b5",
            ])
            self.model_combo.setEditText("facebook/sam-vit-base")  # Default
            self.model_combo.currentTextChanged.connect(self.on_model_changed)
            self.model_path = self.model_combo.currentText().strip()

            model_layout.addWidget(self.model_combo)
            model_group.setLayout(model_layout)
            main_layout.addWidget(model_group)

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
            # Connect to layer selection change
            self.layer_combo.currentIndexChanged.connect(self.on_layer_selected)

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

            # 6. Prediction Button Group
            predict_group = QGroupBox("Prediction")
            predict_layout = QVBoxLayout()
            self.predict_button = QPushButton("Get Inference")
            self.predict_button.clicked.connect(self.on_predict_button_clicked)
            self.predict_button.setEnabled(False)  # Enable after image is loaded
            predict_layout.addWidget(self.predict_button)
            predict_group.setLayout(predict_layout)
            main_layout.addWidget(predict_group)

            # Real-time vs Batch Prediction Option
            self.realtime_checkbox = QCheckBox("Get inference in real time while drawing")
            self.realtime_checkbox.setChecked(False)  # Default to real-time
            settings_layout.addWidget(self.realtime_checkbox)
            self.realtime_checkbox.stateChanged.connect(self.on_realtime_checkbox_changed)

            # Set the main layout
            main_widget.setLayout(main_layout)
            self.dock_widget.setWidget(main_widget)

            # Add dock widget to QGIS
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)

            # initialize the data and tmp directory
            # TODO: move to after checking if docker image is running...and return mounted data folder using docker inspect
            self.data_dir = self.initialize_data_directory()

            # Update the layer (raster) list in the combo box whenever a layer is added or removed
            QgsProject.instance().layersAdded.connect(self.on_layers_added)
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

    def on_project_crs_changed(self):
        """Update the cached project CRS when the project CRS changes."""
        self.project_crs = QgsProject.instance().crs()
        self.iface.messageBar().pushMessage(
            "Info",
            f"Project CRS changed to: {self.project_crs.authid()}",
            level=Qgis.Info,
            duration=5
        )

    def on_realtime_checkbox_changed(self):
        """
        Enable or disable the prediction button based on real-time mode.
        """
        # If real-time mode is checked, disable the prediction button, vice versa
        self.predict_button.setEnabled(not self.realtime_checkbox.isChecked())

        # If real-time mode is unchecked, reset the last prediction time
        if not self.realtime_checkbox.isChecked():
            self.last_pred_time = time.time()

    def update_layer_combo(self):
        """Update the layers combo box with current raster layers in the project"""
        try:
            current_layer_id = self.layer_combo.currentData()
            self.layer_combo.blockSignals(True)
            self.layer_combo.clear()
            self.layer_combo.addItem("Select a layer...", None)

            # Add all raster layers to combo
            for layer in QgsProject.instance().mapLayers().values():
                if isinstance(layer, QgsRasterLayer):
                    self.layer_combo.addItem(layer.name(), layer.id())

            # Restore previous selection if possible
            if current_layer_id:
                index = self.layer_combo.findData(current_layer_id)
                if index != -1:
                    self.layer_combo.setCurrentIndex(index)
            self.layer_combo.blockSignals(False)

        except Exception as e:
            self.logger.error(f"Error updating layer combo: {str(e)}")

    def on_layers_added(self, layers):
        # Only update if any added layer is a QgsRasterLayer
        if any(isinstance(layer, QgsRasterLayer) for layer in layers):
            self.update_layer_combo()

    def is_sam_model(self):
        is_sam = self.model_path.startswith("facebook/sam-")
        return is_sam

    def on_model_changed(self, text=None):
        """1. Enable drawing and embedding only if a SAM model is selected.
           2. Update the embedding path according to model selection."""

        if text is not None:
            self.model_path = text.strip()
        else:
            self.model_path = self.model_combo.currentText().strip()

        is_sam = self.is_sam_model()

        # Drawing section
        self.draw_button.setEnabled(is_sam)
        self.draw_type_combo.setEnabled(is_sam)
        self.realtime_checkbox.setEnabled(is_sam)
        if not is_sam and self.draw_button.isChecked():
            self.draw_button.setChecked(False)
            self.draw_button.setText("Start Drawing")

        # Embedding section
        self.embedding_path_edit.setEnabled(is_sam and not self.no_embedding_radio.isChecked())
        self.embedding_browse_btn.setEnabled(is_sam and not self.no_embedding_radio.isChecked())
        self.embedding_path_edit.clear() if not is_sam else None
        self.no_embedding_radio.setEnabled(is_sam)
        self.load_embedding_radio.setEnabled(is_sam)
        self.save_embedding_radio.setEnabled(is_sam)

        # Update embedding path
        if is_sam:
            self.update_embeddings()

    def update_embeddings(self, image_name=None):
        """Update the embedding path based on the selected model and image"""
        try:
            # Get the image path
            image_path = self.image_path.text()
            if not image_path:
                return

            # Get the image name
            image_name = os.path.splitext(os.path.basename(image_path))[0] if image_name is None else image_name

            # Create embedding directory if it doesn't exist
            embedding_dir = os.path.join(self.data_dir, 'embeddings')
            os.makedirs(embedding_dir, exist_ok=True)

            # Update the embedding path
            model_version = self.model_path.replace('/', '_')
            embedding_path = os.path.join(embedding_dir, f"{image_name}_{model_version}.pt")

            if self.save_embedding_radio.isChecked():
                # Save new embedding
                self.embedding_path_edit.setText(embedding_path)
                self.embedding_browse_btn.setEnabled(True)
                self.embedding_path_edit.setEnabled(True)
                self.iface.messageBar().pushMessage(
                    "Info",
                    f"Will save new embedding for {image_name}.",
                    level=Qgis.Info,
                    duration=5
                )
                self.logger.info(f"Will save new embedding to: {embedding_path}")
            else:
                # Check if embedding file exists
                if os.path.exists(embedding_path):
                    # Found existing embedding
                    self.load_embedding_radio.setChecked(True)
                    self.embedding_path_edit.setEnabled(True)
                    self.embedding_browse_btn.setEnabled(True)

                    # Set the embedding path in the text box
                    self.embedding_path_edit.setText(embedding_path)

                    self.iface.messageBar().pushMessage(
                        "Info",
                        f"Found existing embedding for {image_name}. Will use cached embedding for predictions.",
                        level=Qgis.Info,
                        duration=5
                    )
                    self.logger.info(f"Found existing embedding at: {embedding_path}")
                else:
                    # No existing embedding
                    self.no_embedding_radio.setChecked(True)
                    self.load_embedding_radio.setEnabled(False)  # TODO: what if the user have the embeddings saved somewhere else?
                    # clear the embedding path
                    self.embedding_path_edit.clear()
                    self.embedding_browse_btn.setEnabled(False)
                    self.embedding_path_edit.setEnabled(False)

                    self.iface.messageBar().pushMessage(
                        "Info",
                        f"No existing embedding found for {image_name}. Will generate on the fly on first prediction. Select 'Save new embedding' to save it.",
                        level=Qgis.Info,
                        duration=5
                    )
                    self.logger.info(f"No existing embedding found, will save to: {embedding_path}")

        except Exception as e:
            self.logger.error(f"Error updating embeddings: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to update embeddings: {str(e)}")

    def initialize_image_path(self):
        """Reinitialize the image path input field"""
        self.image_path.clear()
        self.image_path.setPlaceholderText("Enter image path or click Browse...")
        self.image_path.setEnabled(True)
        self.browse_button.setEnabled(True)

    def deactivate_embedding_section(self):
        """Deactivate the embedding section if SAM model is not selected"""
        self.no_embedding_radio.setEnabled(False)
        self.load_embedding_radio.setEnabled(False)
        self.save_embedding_radio.setEnabled(False)
        self.embedding_path_edit.setEnabled(False)
        self.embedding_browse_btn.setEnabled(False)

    def initialize_embedding_path(self):
        """Reinitialize the embedding path input field"""
        self.embedding_path_edit.clear()
        self.embedding_path_edit.setEnabled(False)
        self.embedding_browse_btn.setEnabled(False)
        self.no_embedding_radio.setChecked(True)
        self.load_embedding_radio.setChecked(False)
        self.save_embedding_radio.setChecked(False)


    def on_image_source_changed(self, text):
        """Handle image source selection change"""
        try:
            if text == "File":
                self.image_path.show()
                self.browse_button.show()
                self.layer_combo.hide()
                self.initialize_image_path()
                self.initialize_embedding_path()
                # Deactivate embedding section if SAM model is not selected
                self.deactivate_embedding_section() if not self.is_sam_model() else None
            elif text == "Layer":
                self.image_path.hide()
                self.browse_button.hide()
                self.layer_combo.show()
                self.update_layer_combo()

            # Clear any existing layers
            self.cleanup_previous_session()

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
            raster_layer = QgsRasterLayer(image_path, os.path.basename(image_path))
            if not raster_layer.isValid():
                QMessageBox.warning(None, "Error", "Invalid raster layer")
                return

            # Add raster layer to the project
            QgsProject.instance().addMapLayer(raster_layer)

            # Get image crs and extent
            self.raster_extent, self.raster_width, self.raster_height, self.raster_crs = self.get_current_raster_info(
                raster_layer)
            msg = (
                f"Extent: X min: {self.raster_extent.xMinimum()}, X max: {self.raster_extent.xMaximum()}, "
                f"Y min: {self.raster_extent.yMinimum()}, Y max: {self.raster_extent.yMaximum()}; "
                f"Width: {self.raster_width}; "
                f"Height: {self.raster_height}; "
                f"CRS: {self.raster_crs.authid()}"
            )
            self.iface.messageBar().pushMessage(
                "Selected raster CRS and dimensions",
                msg,
                level=Qgis.Info,
                duration=5
            )

            # Create prediction layers
            self.create_prediction_layers()

            # Update the embedding path if SAM model is selected
            if self.is_sam_model():
                self.update_embeddings()

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

            # TODO: read mount information if the container is started outside QGIS

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
                        cmd = f'echo "{self.sudo_password}" | sudo -S TEMP_DIR={self.tmp_dir} DATA_DIR={self.data_dir} docker-compose -p {self.project_name} -f "{compose_path}" up -d --build'
                        self.progress_status.setText("Building Docker image (this may take a while)...")
                    else:
                        cmd = f'echo "{self.sudo_password}" | sudo -S TEMP_DIR={self.tmp_dir} DATA_DIR={self.data_dir} docker-compose -p {self.project_name} -f "{compose_path}" up -d'
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

        # TODO: handle situations when regretting the drawing
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

                if self.draw_type_combo.currentText() == "Point":
                        self.canvas.setMapTool(self.map_tool)
                elif self.draw_type_combo.currentText() == "Box":
                    self.canvas.setMapTool(self.box_tool)
                else:
                    self.unsetmaptool(self.map_tool)
                    self.unsetmaptool(self.box_tool)

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
            self.draw_button.setText("Start Drawing")

    def cleanup_previous_session(self):
        """Clean up temporary files and layers from previous session"""
        try:
            # Remove existing layers
            if self.prompts_layer and self.prompts_layer.isValid():
                QgsProject.instance().removeMapLayer(self.prompts_layer.id())
                self.prompts_layer = None
            if self.predictions_layer and self.predictions_layer.isValid():
                QgsProject.instance().removeMapLayer(self.predictions_layer.id())
                self.predictions_layer = None

            # Remove existing temporary files
            if self.temp_prompts_geojson and os.path.exists(self.temp_prompts_geojson):
                os.remove(self.temp_prompts_geojson)
                self.prompts_layer = None
            if self.temp_predictions_geojson and os.path.exists(self.temp_predictions_geojson):
                os.remove(self.temp_predictions_geojson)
                self.predictions_layer = None

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

    def on_box_drawn(self, box_geom, start_point, end_point):
        """Handle box drawing completion
        Args:
            box_geom (QgsGeometry): The drawn box geometry
            start_point (QgsPointXY): The starting point of the box
            end_point (QgsPointXY): The ending point of the box
        """

        # Check if the box is valid
        if not box_geom.isGeosValid():
            self.iface.messageBar().pushMessage(
                "Error",
                "Invalid box geometry",
                level=Qgis.Critical,
                duration=3
            )
            return

        # Get raster layer information
        extent, width, height = self.raster_extent, self.raster_width, self.raster_height

        # Calculate pixel coordinates based on start and end points
        pixel_x = int((start_point.x() - extent.xMinimum()) * width / extent.width())
        pixel_y = int((extent.yMaximum() - start_point.y()) * height / extent.height())
        pixel_width = int((end_point.x() - start_point.x()) * width / extent.width())
        pixel_height = int((start_point.y() - end_point.y()) * height / extent.height())
        # Ensure coordinates are within image bounds
        pixel_x = max(0, min(pixel_x, width - 1))
        pixel_y = max(0, min(pixel_y, height - 1))
        pixel_width = max(0, min(pixel_width, width - pixel_x))
        pixel_height = max(0, min(pixel_height, height - pixel_y))
        # Ensure pixel width and height are positive
        pixel_width = max(1, pixel_width)
        pixel_height = max(1, pixel_height)

        # Show message bar with box coordinates
        self.iface.messageBar().pushMessage(
            "Box Info",
            f"Box coordinates sent to server: ({pixel_x}, {pixel_y}, {pixel_x + pixel_width}, {pixel_y + pixel_height})",
            level=Qgis.Info,
            duration=3
        )

        # Create prompt feature
        feature = {
            "type": "Feature",
            "geometry": json.loads(box_geom.asJson()),
            "properties": {
                "id": self.prompt_count,
                "type": "Box",
                "pixel_x": pixel_x,
                "pixel_y": pixel_y,
                "pixel_width": pixel_width,
                "pixel_height": pixel_height,
                "timestamp": time.time()
            }
        }

        # Add prompt feature to layer
        self.add_prompt_to_layer([feature])

        # Increment prompt counter
        self.prompt_count += 1

        # Prepare prompt for server
        prompt = [{
            'type': 'Box',
            'data': {
                "boxes": [[
                    pixel_x,
                    pixel_y,
                    pixel_x + pixel_width,
                    pixel_y + pixel_height
                ]],
            }
        }]

        # Send prediction request if realtime checkbox is checked
        if self.realtime_checkbox.isChecked():
            self.get_prediction(prompt)

        return box_geom

    def get_current_raster_info(self, raster_layer=None):
        """Get current raster layer information for deriving pixel coordinates.
        Returns:
            tuple: extent, width, height of the raster layer
        """

        if not raster_layer:
            raise ValueError("No raster layer found")

        # Get raster dimensions and extent
        extent = raster_layer.extent()
        width = raster_layer.width()
        height = raster_layer.height()
        crs = raster_layer.crs()

        return extent, width, height, crs

    def handle_draw_click(self, point, button):
        """Handle canvas clicks for drawing points or boxes
        Args:
            point (QgsPointXY): The clicked point in map coordinates
            button (Qt.MouseButton): The mouse button that was clicked
        """
        try:
            if not self.draw_button.isChecked() or button != Qt.LeftButton:
                return

            draw_type = self.draw_type_combo.currentText()

            extent, width, height = self.raster_extent, self.raster_width, self.raster_height

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
                        "pixel_y": py,
                        "pixel_width": 0,
                        "pixel_height": 0,
                    }
                }

                # Add timestamp to prompt feature
                prompt_feature["properties"]["timestamp"] = time.time()

                # Add prompt to layer
                self.add_prompt_to_layer([prompt_feature])

                # Increment prompt counter
                self.prompt_count = getattr(self, 'prompt_count', 1) + 1

                # Prepare prompt for server
                prompt = [{
                    'type': 'Point',
                    'data': {
                        "points": [[px, py]],
                        # "labels": [1]
                    }
                }]

                if self.realtime_checkbox.isChecked():
                    self.get_prediction(prompt)
                return point
            else:
                pass

        except Exception as e:
            self.logger.error(f"Error handling draw click: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle drawing: {str(e)}")

    def collect_all_prompts(self):
        """Collect new prompts added after the last_pred_time
        Returns:
            list of dicts with prompt data
        """
        prompts = []

        if self.prompts_layer:
            for feature in self.prompts_layer.getFeatures():
                # Check if the feature is new
                timestamp = feature.attribute('timestamp')
                if timestamp is None or timestamp < self.last_pred_time:
                    continue

                prompt_type = feature['type']
                geom = feature.geometry()
                if prompt_type == 'Point':
                    x = feature['pixel_x']
                    y = feature['pixel_y']
                    prompts.append({'type': 'Point', 'data': {'points': [[x, y]]}}) # TODO: figure out labels for points, when used together with bounding boxes to remove part of the prediction masks
                elif prompt_type == 'Box':
                    x1 = feature['pixel_x']
                    y1 = feature['pixel_y']
                    x2 = feature['pixel_x'] + feature['pixel_width']
                    y2 = feature['pixel_y'] + feature['pixel_height']
                    prompts.append({'type': 'Box', 'data': {'boxes': [[x1, y1, x2, y2]]}})
                else:
                    self.logger.error(f"Unknown prompt type: {prompt_type}")
                    raise ValueError(f"Unknown prompt type: {prompt_type}")
        return prompts

    def on_predict_button_clicked(self):
        """Run prediction: batch if prompts exist, else no-prompts prediction."""
        try:
            prompts = self.collect_all_prompts()  # Implement this to gather all drawn prompts
            # if there are boxes and points in the prompts, we need to run the prediction for both
            if len(prompts) == 0:
                self.iface.messageBar().pushMessage(
                    "Info",
                    "No prompts found. Please draw points or boxes.",
                    level=Qgis.Info,
                    duration=3
                )
                return
            if len(prompts) > 0:
                # Check if there are both points and boxes
                has_points = any(p['type'] == 'Point' for p in prompts)
                has_boxes = any(p['type'] == 'Box' for p in prompts)

                if not (has_points and has_boxes):
                    # Run prediction for all prompts if only one type is present
                    self.get_prediction(prompts)
                else:
                    # Run prediction for points and boxes separately
                    self.iface.messageBar().pushMessage(
                        "Info",
                        f"Running prediction for box and point prompts separatly.",
                        level=Qgis.Info,
                        duration=3
                    )
                    points = [p for p in prompts if p['type'] == 'Point']
                    self.get_prediction(points)
                    boxes = [p for p in prompts if p['type'] == 'Box']
                    self.get_prediction(boxes)
            self.last_pred_time = time.time()  # Update last prediction time
        except Exception as e:
            self.logger.error(f"Error running prediction: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to run prediction: {str(e)}")

    def get_prediction(self, prompts):
        """Get prediction from SAM server and add to predictions layer
        Args:
            prompts: list of dicts with prompt data"""

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

            # TODO: add addtional check on qgis for image path, model path and so on... not just in the controller.py
            # add the model path to the payload if not empty
            self.model_path = self.model_combo.currentText().strip()
            # add model_path to payload if not empty
            if self.model_path:
                payload["model_path"] = self.model_path

            # Show payload in message bar
            # Use:
            if prompts is None or len(prompts) == 0:
                formatted_payload = "No prompts: running full image prediction\n"
            else:
                # print prompts to the logger
                self.logger.debug(f"Prompts: {json.dumps(prompts, indent=2)}")
                formatted_payload = (
                    f"Sending to server:\n"
                    f"- Host image path: {image_path}\n"
                    f"- Host embedding path: {embedding_path}\n"
                    f"- (re)Save embeddings: {save_embeddings}\n"
                    f"- Prompts: {json.dumps(prompts, indent=2)}\n"
                )

            self.iface.messageBar().pushMessage(
                "Server Request",
                formatted_payload,
                level=Qgis.Info,
                duration=5
            )

            # Send request to SAM server
            try:
                if prompts is None or len(prompts) == 0:
                    # No prompts, run full image prediction
                    predict_url = f"{self.server_url}/segment-predict"
                else:
                    # With prompts, run prompt-based prediction
                    predict_url = f"{self.server_url}/sam-predict"

                response = requests.post(
                    predict_url,
                    json=payload,
                    timeout=6000000
                )

                self.logger.debug(f"Server response status: {response.status_code}")
                self.logger.debug(f"Server response text: {response.text}")

                if response.status_code == 200:
                    try:
                        # After the first response from the server, if it was to save the embedding, we need to load it directly instead and avoid saving it again
                        if self.save_embedding_radio.isChecked():
                            self.load_embedding_radio.setChecked(True)
                            self.save_embedding_radio.setChecked(False)
                            self.load_embedding_radio.setEnabled(True)
                            self.update_embeddings()

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

            # Get raster extent and dimensions
            extent, width, height, raster_crs = self.raster_extent, self.raster_width, self.raster_height, self.raster_crs

            # Create coordinate transform if needed
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

                # Add all new features with properties
                for i, feat in enumerate(features):
                    feature = {
                        "type": "Feature",
                        "properties": {
                            "id": self.feature_count + i if hasattr(self, 'feature_count') else i + 1,
                            "scores": feat.get('properties', {}).get('scores', 0),
                        },
                        "geometry": feat['geometry']
                    }
                    self.predictions_geojson["features"].append(feature)

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

            # Enable or disable the path input based on the selected option
            if button == self.save_embedding_radio or button == self.load_embedding_radio:
                self.update_embeddings()

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

    def on_draw_type_changed(self, draw_type):
        """Handle draw type change"""
        try:
            self.logger.debug(f"Draw type changed to: {draw_type}")
            if self.draw_button.isChecked():
                # Switch map tool based on draw type
                if draw_type == "Point":
                    self.canvas.setMapTool(self.map_tool)
                elif draw_type == "Box":
                    self.canvas.setMapTool(self.box_tool)
                else:
                    self.canvas.unsetMapTool(self.map_tool)
                    self.canvas.unsetMapTool(self.box_tool)
            else:
                self.canvas.unsetMapTool(self.map_tool)
                self.canvas.unsetMapTool(self.box_tool)
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

                # create a tmp directory
                self.tmp_dir = os.path.join(data_dir, 'tmp')
                os.makedirs(self.tmp_dir, exist_ok=True)
                self.logger.info(f"Tmp data directory: {data_dir}")

                # Show confirmation
                QMessageBox.information(
                    None,
                    "Data Directory Set",
                    f"Data directory has been set to:\n{data_dir}\n\n"
                    f"Temporary directory has been set to:\n{self.tmp_dir}\n\n"
                    "Please make sure to:\n"
                    "1. Place your input images in this directory\n"
                    "2. Ensure Docker has access to this location\n"
                    "3. Check the temporary directory for any temporary outputs\n"
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
        """Convert host path to container path if within data_dir."""
        if host_path and host_path.startswith(self.data_dir):
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
            if self.is_sam_model():
                self.draw_button.setEnabled(True)

            # Enable prediction (no prompts) controls
            self.predict_button.setEnabled(True)

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
                layer_id = self.layer_combo.itemData(index)
                selected_layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None

                if not selected_layer:
                    return

                # Get imagr crs and extent
                self.raster_extent, self.raster_width, self.raster_height, self.raster_crs = self.get_current_raster_info(selected_layer)
                msg = (
                    f"Extent: X min: {self.raster_extent.xMinimum()}, X max: {self.raster_extent.xMaximum()}, "
                    f"Y min: {self.raster_extent.yMinimum()}, Y max: {self.raster_extent.yMaximum()}; "
                    f"Width: {self.raster_width}; "
                    f"Height: {self.raster_height}; "
                    f"CRS: {self.raster_crs.authid()}"
                )
                self.iface.messageBar().pushMessage(
                    "Selected raster CRS and dimensions",
                    msg,
                    level=Qgis.Info,
                    duration=5
                )

                # Create prediction layers
                self.create_prediction_layers()

                # Check for existing embedding
                layer_source = selected_layer.source()

                image_name = os.path.splitext(os.path.basename(layer_source))[0]
                self.update_embeddings(image_name)

        except Exception as e:
            self.logger.error(f"Error handling layer selection: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle layer selection: {str(e)}")

    def on_image_path_entered(self):
        """Handle manual entry of image path."""
        try:
            image_path = self.image_path.text().strip()
            if not image_path or not os.path.exists(image_path):
                QMessageBox.warning(None, "Error", f"Image file not found: {image_path}")
                return

            valid_extensions = ['.png', '.jpg', '.jpeg', '.tif', '.tiff']
            if not any(image_path.lower().endswith(ext) for ext in valid_extensions):
                QMessageBox.warning(None, "Error", "Invalid file type. Please select an image file (PNG, JPG, TIFF)")
                return

            self.load_image()

        except Exception as e:
            self.logger.error(f"Error processing entered image path: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to load image: {str(e)}")

    def verify_data_directory(self):
        """Verify data directory is properly set up."""
        if not self.data_dir or not os.path.exists(self.data_dir):
            QMessageBox.critical(
                None, "Error",
                "Data directory not configured or not found.\n"
                "Please restart the plugin to configure the data directory."
            )
            return False
        return True

    def add_prompt_to_layer(self, features):
        """Add or append prompt features to prompts layer"""
        try:
            if not features:
                raise ValueError("No features to add")

            # self.logger.debug(f"Incoming prompt features: {json.dumps(features, indent=2)}")

            # Ensure each feature has a 'type' property for styling
            for feat in features:
                if 'properties' not in feat:
                    feat['properties'] = {}
                if 'type' not in feat['properties']:
                    # Guess type from geometry
                    geom_type = feat.get('geometry', {}).get('type', '')
                    if geom_type == 'Point':
                        feat['properties']['type'] = 'Point'
                    elif geom_type == 'Polygon':
                        feat['properties']['type'] = 'Box'
                    else:
                        feat['properties']['type'] = 'Unknown'

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
                    "features": features
                }
            else:
                # Append new features
                self.prompts_geojson['features'].extend(features)

            # Write GeoJSON file
            with open(self.temp_prompts_geojson, 'w') as f:
                json.dump(self.prompts_geojson, f)

            # If layer does not exist, create it
            if not self.prompts_layer or not self.prompts_layer.isValid():
                self.prompts_layer = QgsVectorLayer(
                    self.temp_prompts_geojson,
                    "Drawing Prompts",
                    "ogr"
                )
                if not self.prompts_layer.isValid():
                    raise ValueError("Failed to create valid vector layer")
                QgsProject.instance().addMapLayer(self.prompts_layer)
            else:
                # Reload layer to update features
                self.prompts_layer.dataProvider().reloadData()
                self.prompts_layer.updateExtents()
                self.prompts_layer.triggerRepaint()

            # Apply styling
            self.style_prompts_layer(self.prompts_layer)

            # Update canvas
            self.iface.mapCanvas().refresh()

            # Verify feature count
            actual_count = self.prompts_layer.featureCount()
            expected_count = len(self.prompts_geojson['features'])
            self.logger.info(f"Layer feature count: {actual_count} (added: {expected_count})")

        except Exception as e:
            self.logger.error(f"Error adding prompts: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to add prompts: {str(e)}")