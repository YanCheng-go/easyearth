"""Entry point for the QGIS plugin. Handles plugin registration, menu/toolbar actions, and high-level coordination."""

from datetime import datetime
from qgis.PyQt.QtWidgets import (QAction, QDockWidget, QPushButton, QVBoxLayout,
                                QWidget, QMessageBox, QLabel, QHBoxLayout,
                                QLineEdit, QFileDialog, QComboBox, QGroupBox, QShortcut, QProgressBar, QCheckBox, QButtonGroup, QRadioButton, QApplication, QScrollArea)
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QIcon, QKeySequence, QColor
from qgis.core import (QgsVectorLayer, QgsGeometry,
                      QgsPointXY, QgsProject,
                      QgsWkbTypes, QgsRasterLayer, Qgis, QgsApplication, QgsCategorizedSymbolRenderer,
                      QgsRendererCategory, QgsMarkerSymbol, QgsFillSymbol, QgsCoordinateTransform, QgsSingleSymbolRenderer)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from .core.utils import setup_logger
from .core.prompt_editor import BoxMapTool
from .core.model_manager import ModelManager
import json
import logging
import os
import requests
import shutil
import subprocess
import time
import torch

class EasyEarthPlugin:
    def __init__(self, iface):
        self.iface = iface # QGIS interface instance
        self.logger = setup_logger() # initializes the loger

        # If global logger failed to initialize, create a basic logger
        if self.logger is None:
            self.logger = logging.getLogger('EasyEarth')
            self.logger.addHandler(logging.StreamHandler())
            self.logger.setLevel(logging.DEBUG)

        self.logger.info("Initializing EasyEarth Plugin")

        self.actions = []
        self.menu = 'EasyEarth'
        self.toolbar = self.iface.addToolBar(u'EasyEarth')
        self.toolbar.setObjectName(u'EasyEarth')
        self.plugin_dir = os.path.dirname(__file__) # directory path where the current file is located

        # Docker configuration
        self.project_name = "easyearth_plugin"
        self.sudo_password = None  # Add this to store password temporarily
        self.docker_path = 'docker' if shutil.which('docker') else '/Applications/Docker.app/Contents/Resources/bin/docker' # adds compatibility for macOS
        self.docker_hub_image_name = "maverickmiaow/easyearth"
        # self.docker_hub_image_name = "lgordon99/easyearth"
        self.docker_mode = True

        # Initialize map tools and data
        self.canvas = iface.mapCanvas() # QGIS map canvas instance
        self.point_tool = None # map tool for point selection
        self.points = [] # list to store selected points
        self.rubber_bands = []
        self.docker_process = None
        self.server_port = 3781  # Default port
        self.server_url = f"http://0.0.0.0:{self.server_port}/v1/easyearth"
        self.docker_running = False
        self.server_running = False
        self.action = None
        self.dock_widget = None
        self.point_counter = None
        self.point_layer = None
        self.total_steps = 0
        self.current_step = 0
        self.temp_rubber_band = None
        self.start_point = None
        self.drawn_features = []
        self.drawn_layer = None
        self.data_dir = os.path.join(self.plugin_dir, 'data') # data directory for storing images and embeddings
        self.tmp_dir = os.path.join(self.plugin_dir, 'tmp') # temporary directory for storing temporary files
        self.logs_dir = os.path.join(self.plugin_dir, 'logs') # logs directory for storing logs
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "easyearth", "models") # cache directory for storing models
        self.model_path = None
        self.feature_count = 0 # for generating unique IDs
        self.prompt_count = 0 # for generating unique IDs
        self.temp_prompts_geojson = None # temporary file for storing prompts
        self.temp_predictions_geojson = None
        self.last_pred_time = 0  # timestamp when the real-time prediction is unchecked. or the last batch prediction was done
        self.prompts_layer = None
        self.predictions_layer = None
        self.point_tool = QgsMapToolEmitPoint(self.canvas) # captures mouse clicks on the map canvas and gets the coordinates
        self.point_tool.canvasClicked.connect(self.on_point_drawn) # sets the function to be called when the map is clicked
        self.box_tool = BoxMapTool(self.canvas, self.on_box_drawn) # connects the box drawing tool to the function that handles the drawn box
        self.rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry) # for drawing points
        self.rubber_band.setColor(QColor(255, 0, 0)) # red color for points
        self.rubber_band.setWidth(2) # width of the rubber band for points
        self.temp_rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry) # for drawing temporary boxes
        self.temp_rubber_band.setColor(QColor(255, 0, 0, 50)) # semi-transparent red color for temporary boxes
        self.temp_rubber_band.setWidth(2) # width of the rubber band for temporary boxes
        self.start_point = None
        self.predictions_geojson = None
        self.predictions_layer = None
        self.prompts_geojson = None
        self.prompts_layer = None

        # initialize image crs and extent...
        self.raster_crs = None
        self.raster_extent = None
        self.raster_width = None
        self.raster_height = None
        self.project_crs = QgsProject.instance().crs()

        QgsProject.instance().crsChanged.connect(self.on_project_crs_changed)
        os.environ['LOGS_DIR'] = self.logs_dir

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI"""
        try:
            self.logger.debug("Starting initGui")
            self.logger.info(f"Plugin directory: {self.plugin_dir}")

            icon = QIcon(os.path.join(self.plugin_dir, 'resources/icons/easyearth.png')) # loads the icon from the resources directory

            # Create action with the icon
            self.action = QAction(icon, 'EasyEarth', self.iface.mainWindow()) # creates a toolbar button with the icon and text
            self.action.triggered.connect(self.run) # connects the button click to the run function
            self.action.setEnabled(True) # enables the button

            # Add to QGIS interface
            self.iface.addPluginToMenu('EasyEarth', self.action)
            self.iface.addToolBarIcon(self.action)

            # Create dock widget
            self.dock_widget = QDockWidget('EasyEarth Plugin', self.iface.mainWindow()) # creates a dock widget with the title 'EasyEarth Plugin' within the main window
            self.dock_widget.setObjectName('EasyEarthPluginDock') 

            # Create main widget and layout
            main_widget = QWidget()
            main_layout = QVBoxLayout()

            # 1. Data folder
            data_folder_group = QGroupBox("Data Folder")
            # data_folder_group.setMaximumHeight(100)  # Limit height to avoid excessive space
            data_folder_layout = QHBoxLayout()
            self.data_folder_edit = QLineEdit(self.data_dir)
            self.data_folder_edit.setReadOnly(True)
            self.data_folder_btn = QPushButton("Select folder")
            self.data_folder_btn.clicked.connect(self.select_data_folder)
            data_folder_layout.addWidget(self.data_folder_edit)
            data_folder_layout.addWidget(self.data_folder_btn)
            data_folder_group.setLayout(data_folder_layout)
            main_layout.addWidget(data_folder_group)

            # 2. Run mode
            run_mode_group = QGroupBox("Run Mode")
            # run_mode_group.setMaximumHeight(150)
            run_mode_layout = QVBoxLayout()
            run_mode_info_label = QLabel('You can launch the plugin server either by using Docker if you have it installed or <a href="https://github.com/YanCheng-go/easyearth?tab=readme-ov-file#local-mode">running the server locally outside QGIS</a>.&nbsp;Local mode is required for making use of Mac OS GPUs.')
            run_mode_info_label.setWordWrap(True)
            run_mode_info_label.setOpenExternalLinks(True)  # allows the link to be clickable
            run_mode_info_label.setTextFormat(Qt.RichText)  # enables rich text formatting
            run_mode_layout.addWidget(run_mode_info_label)

            run_mode_button_layout = QHBoxLayout()
            self.docker_mode_button = QPushButton("Docker")
            self.docker_mode_button.setCheckable(True)
            self.docker_mode_button.clicked.connect(lambda: self.run_mode_selected("docker"))
            run_mode_button_layout.addWidget(self.docker_mode_button)
            
            self.local_mode_button = QPushButton("Local")
            self.local_mode_button.setCheckable(True)
            self.local_mode_button.clicked.connect(lambda: self.run_mode_selected("local"))
            run_mode_button_layout.addWidget(self.local_mode_button)
            run_mode_layout.addLayout(run_mode_button_layout)
            run_mode_group.setLayout(run_mode_layout)
            main_layout.addWidget(run_mode_group)

            # 3. Server
            self.server_group = QGroupBox("Server")
            self.server_group.hide()  # Hide by default, will show when run mode is selected
            service_layout = QVBoxLayout()

            # Server status
            status_layout = QHBoxLayout()
            server_label = QLabel("Server status:")
            status_layout.addWidget(server_label)
            self.server_status = QLabel("Checking...")
            status_layout.addWidget(self.server_status)
            status_layout.addStretch()
            service_layout.addLayout(status_layout)
            self.docker_run_btn = QPushButton("Start docker")
            self.docker_run_btn.clicked.connect(self.run_or_stop_container)
            service_layout.addWidget(self.docker_run_btn)

            # API Information
            api_layout = QVBoxLayout()
            api_label = QLabel("API Endpoints:")
            api_label.setStyleSheet("font-weight: bold;")
            self.api_info = QLabel(f"Base URL: http://0.0.0.0:{self.server_port}/v1/easyearth\n"
                                   f"Inference: /predict\n"
                                   f"Health check: /ping")
            self.api_info.setWordWrap(True)
            api_layout.addWidget(api_label)
            api_layout.addWidget(self.api_info)
            service_layout.addLayout(api_layout)

            self.server_group.setLayout(service_layout)
            main_layout.addWidget(self.server_group)

            # 4. Model Selection Group
            self.model_group = QGroupBox("Segmentation Model")
            self.model_group.hide() # Hide by default, will show when server is online
            model_layout = QHBoxLayout()

            self.model_combo = QComboBox()
            self.model_combo.setEditable(True)
            # Add common models
            self.model_combo.addItems([
                "facebook/sam-vit-base",
                "facebook/sam-vit-large",
                "facebook/sam-vit-huge",
                "restor/tcd-segformer-mit-b5",
            ])
            self.model_combo.setEditText("facebook/sam-vit-base") # default
            self.model_combo.currentTextChanged.connect(self.on_model_changed)
            self.model_path = self.model_combo.currentText().strip()

            model_layout.addWidget(self.model_combo)
            self.model_group.setLayout(model_layout)
            main_layout.addWidget(self.model_group)

            # 5. Image Source Group
            self.image_group = QGroupBox("Image Source")
            self.image_group.hide()  # Hide by default, will show when model is selected
            image_layout = QVBoxLayout()

            # Image source selection
            source_layout = QHBoxLayout()
            source_label = QLabel("Source:")
            self.source_combo = QComboBox()
            self.source_combo.addItems(["File", "Layer", "Link"])
            self.source_combo.currentTextChanged.connect(self.on_image_source_changed)
            source_layout.addWidget(source_label)
            source_layout.addWidget(self.source_combo)
            image_layout.addLayout(source_layout)

            # File input
            file_layout = QHBoxLayout()
            image_path_label = QLabel("Image path:")
            self.image_path = QLineEdit("")
            self.image_path.setReadOnly(True)
            self.image_path.setPlaceholderText("No image selected")
            self.browse_button = QPushButton("Select image")
            self.browse_button.clicked.connect(self.browse_image)
            file_layout.addWidget(image_path_label)
            file_layout.addWidget(self.image_path)
            file_layout.addWidget(self.browse_button)

            # Link input
            self.download_button = QPushButton("Download")
            self.download_button.hide()
            self.download_button.clicked.connect(self.on_download_button_clicked)
            file_layout.addWidget(self.download_button)

            self.image_download_progress_bar = QProgressBar()
            self.image_download_progress_bar.setMinimum(0)
            self.image_download_progress_bar.setMaximum(100)
            self.image_download_progress_bar.hide()
            file_layout.addWidget(self.image_download_progress_bar)  # <-- Add to file_layout

            self.downloading_progress_status = QLabel()
            self.downloading_progress_status.setWordWrap(True)
            self.downloading_progress_status.hide()
            file_layout.addWidget(self.downloading_progress_status)  # <-- Add to file_layout

            # Layer selection
            self.layer_dropdown = QComboBox() # displays a list of available raster layers in the project
            self.layer_dropdown.hide()
            file_layout.addWidget(self.layer_dropdown)
            # Connect to layer selection change
            self.layer_dropdown.currentIndexChanged.connect(self.on_layer_selected)

            image_layout.addLayout(file_layout)
            self.image_group.setLayout(image_layout)
            main_layout.addWidget(self.image_group)

            # 6. Embedding Settings Group
            self.embedding_group = QGroupBox("Embedding Settings")
            self.embedding_group.hide()  # Hide by default, will show when image is selected and SAM model is chosen
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

            self.embedding_group.setLayout(embedding_layout)
            main_layout.addWidget(self.embedding_group)

            # 7. Drawing and Prediction Settings Group
            self.drawing_group = QGroupBox("Drawing and Prediction Settings")
            self.drawing_group.hide()  # Hide by default, will show when image is loaded
            settings_layout = QVBoxLayout()

            # Drawing type selection
            type_layout = QHBoxLayout()
            type_label = QLabel("Draw type:")
            self.draw_type_dropdown = QComboBox()
            self.draw_type_dropdown.addItems(["Point", "Box"])
            self.draw_type_dropdown.setItemData(2, False, Qt.UserRole - 1)  # Disable Text option
            self.draw_type_dropdown.currentTextChanged.connect(self.on_draw_type_changed)
            type_layout.addWidget(type_label)
            type_layout.addWidget(self.draw_type_dropdown)
            settings_layout.addLayout(type_layout)

            # Drawing and undoing buttons
            button_layout = QHBoxLayout()
            self.draw_button = QPushButton("Start drawing")
            self.draw_button.setCheckable(True)
            self.draw_button.clicked.connect(self.toggle_drawing)
            self.draw_button.setEnabled(False) # enabled after image is loaded
            button_layout.addWidget(self.draw_button)
            
            self.undo_button = QPushButton("Undo last drawing")
            self.undo_button.clicked.connect(self.undo_last_drawing)
            self.undo_button.setEnabled(False) # enable after drawing starts
            self.undo_shortcut = QShortcut(QKeySequence.Undo, self.iface.mainWindow())
            self.undo_shortcut.activated.connect(self.undo_last_drawing)  # Connect shortcut to undo function
            button_layout.addWidget(self.undo_button)
            settings_layout.addLayout(button_layout)

            self.drawing_group.setLayout(settings_layout)
            main_layout.addWidget(self.drawing_group)

            # 8. Prediction Button Group
            self.predict_group = QGroupBox("Prediction")
            self.predict_group.hide()  # Hide by default, will show when image is loaded
            predict_layout = QVBoxLayout()
            self.predict_button = QPushButton("Run inference")
            self.predict_button.clicked.connect(self.on_predict_button_clicked)
            self.predict_button.setEnabled(False)  # Enable after image is loaded
            predict_layout.addWidget(self.predict_button)
            self.predict_group.setLayout(predict_layout)
            main_layout.addWidget(self.predict_group)

            # Real-time vs Batch Prediction Option
            self.realtime_checkbox = QCheckBox("Get inference in real time while drawing")
            self.realtime_checkbox.setChecked(False) # Default to not real-time
            settings_layout.addWidget(self.realtime_checkbox)
            self.realtime_checkbox.stateChanged.connect(self.on_realtime_checkbox_changed)

            # Set the main layout
            main_layout.addStretch()
            main_widget.setLayout(main_layout)
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setWidget(main_widget)
            self.dock_widget.setWidget(scroll_area)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget) # Add dock widget to QGIS

            # initialize the data and tmp directory
            # TODO: move to after checking if docker image is running...and return mounted data folder using docker inspect
            # self.data_dir = self.initialize_data_directory()

            # Update the layer (raster) list in the combo box whenever a layer is added or removed
            QgsProject.instance().layersAdded.connect(self.update_layer_dropdown)
            QgsProject.instance().layersRemoved.connect(self.update_layer_dropdown)

            # Connect to QGIS quit signal
            QgsApplication.instance().aboutToQuit.connect(self.cleanup_docker)

            # # Check if the container is running on startup
            # self.inspect_running_container()

            # Check GPU availability on startup
            self.check_gpu_availability()

            self.logger.debug("Finished initGui setup")
        except Exception as e:
            self.logger.error(f"Error in initGui: {str(e)}")
            self.logger.exception("Full traceback:")

    def run(self):
        """Run method that loads and starts the plugin"""
        if self.dock_widget.isVisible():
            self.dock_widget.hide()
        else:
            self.dock_widget.show()

    def check_gpu_availability(self):
        """Check if GPU is available for model inference"""
        if torch.backends.mps.is_available():
            self.iface.messageBar().pushMessage("Info", "MPS GPU is available", level=Qgis.Info, duration=5)
            return "mps"
        elif torch.cuda.is_available():
            self.iface.messageBar().pushMessage("Info", "CUDA GPU is available", level=Qgis.Info, duration=5)
            return "cuda"
        else:
            self.iface.messageBar().pushMessage("Warning", "No GPU available, using CPU", level=Qgis.Warning, duration=5)
            return "cpu"

    def check_server_status(self):
        """Check if the server is running by pinging it"""

        try:
            response = requests.get(f"http://0.0.0.0:{self.server_port}/v1/easyearth/ping", timeout=2)

            if response.status_code == 200:
                self.server_status.setText("Online")
                self.server_status.setStyleSheet("color: green;")
                self.server_running = True
                self.docker_running = True
                self.docker_run_btn.show()
                self.docker_run_btn.setText("Stop server")
                self.model_group.show()  # Show model selection group when server is online
                self.image_group.show()  # Show image source group when server is online
            else:
                self.server_status.setText("Error")
                self.server_status.setStyleSheet("color: red;")
                self.server_running = False
                self.docker_running = False
                self.docker_run_btn.setText("Start docker")
        except requests.exceptions.RequestException:
            self.server_status.setText("Offline")
            self.server_status.setStyleSheet("color: red;")
            self.server_running = False
            self.docker_running = False
            self.docker_run_btn.setText("Start docker")

    def run_mode_selected(self, mode):
        """Handle run mode selection (Docker or Local)"""
        self.server_group.show()  # Show server group when a mode is selected
        # Start periodic server status check
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_server_status)
        self.status_timer.start(5000)  # Check every 5 seconds

        if mode == 'docker':
            self.local_mode_button.setChecked(False)
            self.docker_mode = True
            self.docker_run_btn.show()
        elif mode == 'local':
            self.docker_mode_button.setChecked(False)
            self.docker_mode = False

            if not self.server_running:
                self.docker_run_btn.hide() # hides the button if in local mode

    def start_server(self):
        if self.docker_mode_button.isChecked():
            logs_dir = os.path.join(self.plugin_dir, 'logs')
            cache_dir = os.path.expandvars("$HOME/.cache/easyearth/models")
            docker_run_cmd = (f"{self.docker_path} rm -f easyearth 2>/dev/null || true && " # removes the container if it already exists
                            f"{self.docker_path} pull {self.docker_hub_image_name} && " # pulls the latest image from docker hub
                            f"{self.docker_path} run -d --name easyearth -p 3781:3781 "
                            f"-v \"{self.data_dir}\":/usr/src/app/data " # mounts the data directory in the container
                            f"-v \"{self.tmp_dir}\":/usr/src/app/tmp " # mounts the tmp directory in the container
                            f"-v \"{logs_dir}\":/usr/src/app/logs " # mounts the logs directory in the container
                            f"-v \"{cache_dir}\":/usr/src/app/.cache/models " # mounts the cache directory in the container
                            f"{self.docker_hub_image_name}")
            result = subprocess.run(docker_run_cmd, capture_output=True, text=True, shell=True)
            self.iface.messageBar().pushMessage("Info",
                                                f"Starting server...\nRunning command: {result}",
                                                level=Qgis.Info,
                                                duration=5)
            
            if result.returncode == 0:
                self.docker_running = True

    def stop_server(self):
        if self.docker_mode_button.isChecked():
            result = subprocess.run(f"{self.docker_path} stop easyearth && {self.docker_path} rm easyearth", capture_output=True, text=True, shell=True)
            self.docker_hub_process = None
            self.docker_running = False
        else:
            result = subprocess.run('kill $(lsof -t -i:3781)', capture_output=True, text=True, shell=True) # kills the process running on port 3781

        self.iface.messageBar().pushMessage("Info",
                                            f"Stopping server with command: {result}",
                                            level=Qgis.Info,
                                            duration=5)

    def run_or_stop_container(self):
        if not self.docker_running: # if the docker container is not running, start it
            self.data_folder_edit.setReadOnly(True)
            self.data_folder_btn.setEnabled(False)
            self.docker_run_btn.setText("Stop server")
            self.start_server()
        else: # if the container is running, stop it
            self.stop_server()
            self.data_folder_edit.setReadOnly(False)
            self.data_folder_btn.setEnabled(True)
            self.docker_run_btn.setText("Start docker")

            if self.local_mode_button.isChecked():
                self.docker_run_btn.hide()

    def select_data_folder(self):
        folder = QFileDialog.getExistingDirectory(None, "Select Data Folder", self.data_folder_edit.text()) # opens a dialog to select a folder

        if folder: # if a folder is selected
            self.data_folder_edit.setText(folder)
            self.data_dir = folder

        if not os.path.exists(self.data_dir):
            QMessageBox.warning(None, "Error", f"Data directory does not exist: {self.data_dir}")
            return
        
        self.iface.messageBar().pushMessage("Info", f"Data folder set to: {self.data_dir}", level=Qgis.Info, duration=5)

    def on_image_source_changed(self, text):
        """Handle image source selection change"""

        try:
            if text == "File":
                self.image_path.show()
                self.image_path.setReadOnly(True)
                self.browse_button.show()
                self.layer_dropdown.hide()
                self.download_button.hide()
                self.initialize_image_path()
                self.initialize_embedding_path()
                self.deactivate_embedding_section() if not self.is_sam_model() else None
            elif text == "Layer":
                self.image_path.hide()
                self.browse_button.hide()
                self.download_button.hide()
                self.layer_dropdown.show()
                self.update_layer_dropdown()
                self.embedding_group.setVisible(self.is_sam_model()) # show embedding section if SAM model is selected
            elif text == "Link":
                self.image_path.show()
                self.image_path.setReadOnly(False)
                self.browse_button.hide()
                self.download_button.show()
                self.layer_dropdown.hide()
                self.image_path.setPlaceholderText("Enter image URL (http/https)...")
                self.image_path.clear()
                self.initialize_embedding_path()
                self.deactivate_embedding_section() if not self.is_sam_model() else None

            self.cleanup_previous_session() # clears any existing layers

        except Exception as e:
            self.logger.error(f"Error in image source change: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to change image source: {str(e)}")

    def on_download_button_clicked(self):
        """Download image from URL and switch to File mode."""
        try:
            image_url = self.image_path.text().strip()

            if not (image_url.startswith("http://") or image_url.startswith("https://")):
                QMessageBox.warning(None, "Error", "Please enter a valid image URL.")
                return

            self.download_button.hide()
            self.image_download_progress_bar.setValue(0)
            self.image_download_progress_bar.setMaximum(100)
            self.image_download_progress_bar.show()
            self.downloading_progress_status.setText("Downloading image...")
            self.downloading_progress_status.show()

            local_filename = os.path.basename(image_url.split("?")[0])
            save_path = os.path.join(self.data_dir, local_filename)
            response = requests.get(image_url, stream=True)
            total = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(save_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            percent = int(downloaded * 100 / total)
                            self.image_download_progress_bar.setValue(percent)
                            QApplication.processEvents()

            self.image_download_progress_bar.hide()
            self.downloading_progress_status.hide()

            # Switch to File mode and update path
            self.source_combo.setCurrentText("File")
            self.image_path.setText(save_path)
            self.load_image()
        except Exception as e:
            self.logger.error(f"Error downloading image: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to download image: {str(e)}")

    def on_project_crs_changed(self):
        """Update the cached project CRS when the project CRS changes."""

        self.project_crs = QgsProject.instance().crs()
        self.iface.messageBar().pushMessage("Info", f"Project CRS changed to: {self.project_crs.authid()}", level=Qgis.Info, duration=5)

    def on_realtime_checkbox_changed(self):
        """Enable or disable the prediction button based on real-time mode."""
        self.predict_button.setEnabled(not self.realtime_checkbox.isChecked()) # if real-time mode is checked, disable the prediction button, vice versa

        # If real-time mode is unchecked, reset the last prediction time
        if not self.realtime_checkbox.isChecked():
            self.last_pred_time = time.time()

    def update_layer_dropdown(self):
        """Update the layers dropdown with the current raster layers in the project"""

        try:
            current_layer_id = self.layer_dropdown.currentData()
            self.layer_dropdown.blockSignals(True)
            self.layer_dropdown.clear()
            self.layer_dropdown.addItem("Select a layer...", None)

            # Add all raster layers to combo
            for layer in QgsProject.instance().mapLayers().values():
                if isinstance(layer, QgsRasterLayer):
                    self.layer_dropdown.addItem(layer.name(), layer.id())

            # Restore previous selection if possible
            if current_layer_id:
                index = self.layer_dropdown.findData(current_layer_id)

                if index != -1:
                    self.layer_dropdown.setCurrentIndex(index)
            self.layer_dropdown.blockSignals(False)

        except Exception as e:
            self.logger.error(f"Error updating layer combo: {str(e)}")

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
        self.draw_type_dropdown.setEnabled(is_sam)
        self.realtime_checkbox.setEnabled(is_sam)

        if not is_sam:
            self.draw_button.setChecked(False)
            self.draw_button.setText("Start drawing")

        # Embedding section
        self.embedding_path_edit.setEnabled(is_sam and not self.no_embedding_radio.isChecked())
        self.embedding_browse_btn.setEnabled(is_sam and not self.no_embedding_radio.isChecked())
        self.embedding_path_edit.clear() if not is_sam else None
        self.no_embedding_radio.setChecked(True)
        self.no_embedding_radio.setEnabled(is_sam)
        self.load_embedding_radio.setEnabled(is_sam)
        self.save_embedding_radio.setEnabled(is_sam)
        self.embedding_group.setVisible(is_sam)

        # Update embedding path
        if is_sam:
            self.update_embeddings()

    def update_embeddings(self, image_name=None):
        """Update the embedding path based on the selected model and image"""
        try:
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
        self.image_path.setPlaceholderText("No image selected")
        self.image_path.setEnabled(True)
        self.browse_button.setEnabled(True)

    def browse_image(self):
        """Open file dialog for image selection"""
        try:
            initial_dir = self.data_dir if os.path.exists(self.data_dir) else ""
            file_path, _ = QFileDialog.getOpenFileName(
                self.dock_widget,
                "Select Image File",
                initial_dir,
                "Image Files (*.png *.jpg *.jpeg *.tif *.tiff *.JPG *.JPEG *.PNG *.TIF *.TIFF);;All Files (*.*)"
            )

            if file_path:
                # Verify the file is within data_dir
                if not os.path.commonpath([file_path]).startswith(os.path.commonpath([self.data_dir])):
                    QMessageBox.warning(None, "Invalid Location", f"Please select an image from within the data directory:\n{self.data_dir}")
                    return

                self.image_path.setText(file_path)
                self.load_image() # loads the image to canvas

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

            QgsProject.instance().addMapLayer(raster_layer) # adds raster layer to the project

            # Get image crs and extent
            self.raster_extent, self.raster_width, self.raster_height, self.raster_crs = self.get_current_raster_info(raster_layer)
            raster_properties = (f"Extent: X min: {self.raster_extent.xMinimum()}, X max: {self.raster_extent.xMaximum()}, "
                                 f"Y min: {self.raster_extent.yMinimum()}, Y max: {self.raster_extent.yMaximum()}; "
                                 f"Width: {self.raster_width}; "
                                 f"Height: {self.raster_height}; "
                                 f"CRS: {self.raster_crs.authid()}")
            self.iface.messageBar().pushMessage("Selected raster CRS and dimensions", raster_properties, level=Qgis.Info, duration=5)
            self.create_prediction_layers()

            if self.is_sam_model():
                self.update_embeddings()

            self.embedding_group.setVisible(self.is_sam_model())  # Show embedding section if SAM model is selected
            self.drawing_group.setVisible(True)  # Show drawing section when image is loaded
            self.predict_group.setVisible(True)  # Show prediction section when image is loaded
        except Exception as e:
            self.logger.error(f"Error loading image: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to load image: {str(e)}")

    def deactivate_embedding_section(self):
        """Deactivate the embedding section if SAM model is not selected"""

        self.embedding_group.setVisible(False)

    def initialize_embedding_path(self):
        """Reinitialize the embedding path input field"""
        self.embedding_path_edit.clear()
        self.embedding_path_edit.setEnabled(False)
        self.embedding_browse_btn.setEnabled(False)
        self.no_embedding_radio.setChecked(True)
        self.load_embedding_radio.setChecked(False)
        self.save_embedding_radio.setChecked(False)

    def style_prompts_layer(self, layer):
        """Style the prompts layer with different symbols for points and boxes"""

        try:
            existing_types = list(layer.dataProvider().uniqueValues(layer.fields().lookupField('type')))
            categories = []

            if 'Point' in existing_types:
                point_symbol = QgsMarkerSymbol.createSimple({'name': 'circle', 'size': '3', 'color': '255,0,0,255'}) # red circle for points
                categories.append(QgsRendererCategory('Point', point_symbol, 'Point'))
            if 'Box' in existing_types:
                box_symbol = QgsFillSymbol.createSimple({'color': '255,255,0,50', 'outline_color': '255,0,0,255', 'outline_width': '0.8'}) # semi-transparent yellow fill with red outline for boxes
                categories.append(QgsRendererCategory('Box', box_symbol, 'Box'))

            # Create and apply the renderer
            renderer = QgsCategorizedSymbolRenderer('type', categories)
            layer.setRenderer(renderer)
            layer.triggerRepaint()

        except Exception as e:
            self.logger.error(f"Error styling prompts layer: {str(e)}")

    def style_predictions_layer(self, layer):
        """Style the predictions layer"""
        
        try:
            symbol = QgsFillSymbol.createSimple({'color': '0,255,0,50', # semi-transparent green
                                                 'outline_color': '0,255,0,255', # solid green outline
                                                 'outline_width': '0.8',
                                                 'outline_style': 'solid',
                                                 'style': 'solid'})

            # Create and apply the renderer
            renderer = QgsSingleSymbolRenderer(symbol)
            layer.setRenderer(renderer)
            layer.setOpacity(0.5) # 50% transparent
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

    def toggle_drawing(self, checked):
        """Toggle drawing mode"""

        try:
            self.logger.info(f"Toggle drawing called with checked={checked}")

            if checked:
                self.logger.info("Starting new drawing session")
                self.draw_button.setText("Stop Drawing")
                self.undo_button.setEnabled(True)
                
                if self.draw_type_dropdown.currentText() == "Point":
                    self.canvas.setMapTool(self.point_tool)
                elif self.draw_type_dropdown.currentText() == "Box":
                    self.canvas.setMapTool(self.box_tool)
                else:
                    self.unsetMapTool(self.point_tool)
                    self.unsetMapTool(self.box_tool)

                self.logger.info("Drawing session started successfully")
            else:
                self.canvas.unsetMapTool(self.point_tool)
                self.draw_button.setText("Start drawing")
                self.undo_button.setEnabled(False)
                self.logger.info("Stopping drawing session")

        except Exception as e:
            self.logger.error(f"Failed to toggle drawing: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to start drawing: {str(e)}")
            self.draw_button.setChecked(False)
            self.draw_button.setText("Start Drawing")

    def on_point_drawn(self, point, button):
        """Handle canvas clicks for drawing points or boxes
        Args:
            point (QgsPointXY): The clicked point in map coordinates
            button (Qt.MouseButton): The mouse button that was clicked
        """

        try:
            if not self.draw_button.isChecked() or button != Qt.LeftButton:
                return None

            draw_type = self.draw_type_dropdown.currentText()
            extent, width, height, raster_crs = self.raster_extent, self.raster_width, self.raster_height, self.raster_crs

            # Transform point to raster CRS if needed
            if self.project_crs != raster_crs and raster_crs is not None:
                transform = QgsCoordinateTransform(self.project_crs, raster_crs, QgsProject.instance())
                point = transform.transform(point)

            if draw_type == "Point":
                # Calculate pixel coordinates
                px = int((point.x() - extent.xMinimum()) * width / extent.width())
                py = int((extent.yMaximum() - point.y()) * height / extent.height())

                # Ensure coordinates are within image bounds
                px = max(0, min(px, width - 1))
                py = max(0, min(py, height - 1))

                # Show coordinates in message bar
                self.iface.messageBar().pushMessage("Point Info",
                                                    f"Map coordinates: ({point.x():.2f}, {point.y():.2f})\n"
                                                    f"Pixel coordinates sent to server: ({px}, {py})",
                                                    level=Qgis.Info,
                                                    duration=3)

                # Create prompt feature
                point_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [point.x(), point.y()]
                    },
                    "properties": {
                        "id": self.prompt_count,
                        "type": "Point",
                        "pixel_x": px,
                        "pixel_y": py,
                        "pixel_width": 0,
                        "pixel_height": 0,
                    }
                }

                point_feature["properties"]["timestamp"] = time.time() # adds timestamp to prompt feature
                self.add_features_to_layer([point_feature], "prompts") # adds point to layer
                self.prompt_count += + 1 # increments prompt counter

                # Prepare prompt for server
                prompt = [{'type': 'Point', 'data': {"points": [[px, py]]}}]

                if self.realtime_checkbox.isChecked():
                    self.get_prediction(prompt)
                return point
            return None

        except Exception as e:
            self.logger.error(f"Error handling draw click: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle drawing: {str(e)}")
            return None

    def undo_last_drawing(self):
        self.prompts_geojson['features'] = self.prompts_geojson['features'][:-1] # removes the last point from the prompts geojson
        self.prompt_count = self.prompt_count - 1 if self.prompt_count > 0 else 0  # decrements the prompt counter
        self.add_features_to_layer([], "prompts")

        if self.realtime_checkbox.isChecked():
            self.predictions_geojson['features'] = self.predictions_geojson['features'][:-1] # removes the last point from the prompts geojson
            self.add_features_to_layer([], "predictions")

    def on_box_drawn(self, box_geom, start_point, end_point):
        """Handle box drawing completion
        Args:
            box_geom (QgsGeometry): The drawn box geometry
            start_point (QgsPointXY): The starting point of the box
            end_point (QgsPointXY): The ending point of the box
        """

        # Check if the box is valid
        if not box_geom.isGeosValid():
            self.iface.messageBar().pushMessage("Error", "Invalid box geometry", level=Qgis.Critical, duration=3)
            return

        # Get raster layer information
        extent, width, height, raster_crs = self.raster_extent, self.raster_width, self.raster_height, self.raster_crs

        # Transform start and end points to raster CRS
        if self.project_crs != raster_crs and raster_crs is not None:
            transform = QgsCoordinateTransform(self.project_crs, raster_crs, QgsProject.instance())
            start_point = transform.transform(start_point)
            end_point = transform.transform(end_point)
            # convert to box_geom
            box_geom = QgsGeometry.fromPolygonXY([[
                start_point,
                QgsPointXY(end_point.x(), start_point.y()),
                end_point,
                QgsPointXY(start_point.x(), end_point.y()),
                start_point
            ]])

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

        self.add_features_to_layer([feature], "prompts") # adds prompt feature to layer
        self.prompt_count += 1 # increments prompt counter

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

    def add_features_to_layer(self, features, layer_type='prompts', crs=None):
        """
        Add or append features to the specified layer (prompts or predictions).
        Args:
            features: list of GeoJSON features
            layer_type: 'prompts' or 'predictions'
            crs: coordinate reference system for the features
        """
        try:
            extent, width, height, raster_crs = self.raster_extent, self.raster_width, self.raster_height, self.raster_crs

            # Set up layer-specific variables
            if layer_type == 'prompts':
                geojson_attr = 'prompts_geojson'
                temp_geojson = self.temp_prompts_geojson
                layer_attr = 'prompts_layer'
                layer_name = "Drawing Prompts"
                style_func = self.style_prompts_layer
                
                # Ensure 'type' property for styling
                for feat in features:
                    if 'properties' not in feat:
                        feat['properties'] = {}
                        
                    if 'type' not in feat['properties']:
                        geom_type = feat.get('geometry', {}).get('type', '')
                        feat['properties']['type'] = 'Point' if geom_type == 'Point' else 'Box' if geom_type == 'Polygon' else 'Unknown'

                # convert project crs to raster crs
                transform = QgsCoordinateTransform(self.project_crs, raster_crs, QgsProject.instance())
                
                if self.project_crs != raster_crs:
                    self.iface.messageBar().pushMessage("Warning",
                                                        f"Project CRS ({self.project_crs.authid()}) does not match raster CRS ({raster_crs.authid()}). "
                                                        "Transforming prompts crs to match raster CRS.",
                                                        level=Qgis.Warning,
                                                        duration=5)
                    
                    for feature in features:
                        geom_json = feature.get('geometry')
                        
                        if geom_json and geom_json['type'] == 'Polygon':
                            map_coords = []
                            
                            for ring in geom_json['coordinates']:
                                map_ring = []
                                
                                for map_x, map_y in ring:
                                    point = QgsPointXY(map_x, map_y)
                                    point = transform.transform(point)
                                    map_ring.append(point)
                                
                                map_coords.append(map_ring)
                            
                            feature['geometry']['coordinates'] = [[(p.x(), p.y()) for p in ring] for ring in map_coords]
                        
                        if geom_json and geom_json['type'] == 'Point':
                            map_x, map_y = geom_json['coordinates']
                            point = QgsPointXY(map_x, map_y)
                            point = transform.transform(point)
                            feature['geometry']['coordinates'] = [point.x(), point.y()]

            elif layer_type == 'predictions':
                geojson_attr = 'predictions_geojson'
                temp_geojson = self.temp_predictions_geojson
                layer_attr = 'predictions_layer'
                layer_name = "SAM Predictions"
                style_func = self.style_predictions_layer

                # Assign unique ids
                if not hasattr(self, 'feature_count'):
                    self.feature_count = 0
                start_id = self.feature_count
                features = [{
                    "type": "Feature",
                    "properties": {
                        "id": start_id + i,
                        "scores": feat.get('properties', {}).get('scores', 0),
                    },
                    "geometry": feat['geometry']
                } for i, feat in enumerate(features)]
                self.feature_count += len(features)

                # TODO: fix no coordinate system input impact to 4326
                # Transform pixel to map coordinates for polygons if feature_crs is None
                if crs is None:
                    # Transform pixel coordinates to map coordinates
                    self.iface.messageBar().pushMessage("Warning",
                                                        f"Prediction CRS is None. Transforming pixel coordinates to project coordinates.",
                                                        level=Qgis.Warning,
                                                        duration=5)
                    transform = QgsCoordinateTransform(raster_crs, self.project_crs, QgsProject.instance())
                    
                    for feature in features:
                        geom_json = feature.get('geometry')
                        
                        if geom_json and geom_json['type'] == 'Polygon':
                            map_coords = []
                            
                            for ring in geom_json['coordinates']:
                                map_ring = []
                                
                                for pixel_coord in ring:
                                    map_x = extent.xMinimum() + (pixel_coord[0] * extent.width() / width)
                                    map_y = extent.yMaximum() - (pixel_coord[1] * extent.height() / height)
                                    point = QgsPointXY(map_x, map_y)
                                    point = transform.transform(point)
                                    map_ring.append(point)
                                map_coords.append(map_ring)
                            feature['geometry']['coordinates'] = [[(p.x(), p.y()) for p in ring] for ring in map_coords]

            else:
                raise ValueError("Invalid layer_type")

            # Prepare or update GeoJSON
            geojson = getattr(self, geojson_attr, None)
            
            if not geojson:
                geojson = {
                    "type": "FeatureCollection",
                    "features": features,
                    "crs": {
                        "type": "name",
                        "properties": {
                            "name": self.raster_crs.authid()
                        }
                    }
                }
            else:
                geojson['features'].extend(features)
                
            setattr(self, geojson_attr, geojson)

            # Write GeoJSON file
            with open(temp_geojson, 'w') as f:
                json.dump(geojson, f)

            # Create or update layer
            layer = getattr(self, layer_attr, None)
            
            if not layer:
                layer = QgsVectorLayer(temp_geojson, layer_name, "ogr")
                layer.setCrs(self.raster_crs)
                layer.setExtent(self.raster_extent)

                if not layer.isValid():
                    raise ValueError("Failed to create valid vector layer")
                QgsProject.instance().addMapLayer(layer)
                setattr(self, layer_attr, layer)
            else:
                layer.dataProvider().reloadData()
                layer.updateExtents()
                layer.triggerRepaint()

            # Apply styling
            style_func(layer)

            # Refresh canvas
            self.iface.mapCanvas().refresh()

            # Log feature count
            actual_count = layer.featureCount()
            expected_count = len(geojson['features'])
            self.logger.info(f"{layer_name} feature count: {actual_count} (added: {expected_count})")

        except Exception as e:
            self.logger.error(f"Error adding {layer_type}: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to add {layer_type}: {str(e)}")

    @staticmethod
    def get_current_raster_info(raster_layer=None):
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
            if self.is_sam_model():
                if len(prompts) == 0:
                    self.iface.messageBar().pushMessage(
                        "Info",
                        "No prompts found. Please draw points or boxes.",
                        level=Qgis.Info,
                        duration=3
                    )
                    return
                else:
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
            else:
                # For other models, run prediction without prompts
                self.iface.messageBar().pushMessage(
                    "Info",
                    "Running prediction without prompts.",
                    level=Qgis.Info,
                    duration=3
                )
                self.get_prediction(prompts)
            self.last_pred_time = time.time()  # Update last prediction time
        except Exception as e:
            self.logger.error(f"Error running prediction: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to run prediction: {str(e)}")

    def get_prediction(self, prompts):
        """Get prediction from SAM server and add to predictions layer
        Args:
            prompts: list of dicts with prompt data"""

        try:
            # Show loading indicator
            self.iface.messageBar().pushMessage("Info", "Getting prediction...", level=Qgis.Info)
            QApplication.setOverrideCursor(Qt.WaitCursor)

            # Get the image path and convert for container
            image_path = self.image_path.text()

            if not os.path.exists(image_path):
                raise ValueError(f"Image file not found: {image_path}")

            # Initialize embedding variables
            embedding_path = None
            container_embedding_path = None
            save_embeddings = False

            # Handle embedding settings
            if self.load_embedding_radio.isChecked() and self.load_embedding_radio.isEnabled():
                embedding_path = self.embedding_path_edit.text().strip()

                if not embedding_path:
                    raise ValueError("Please select an embedding file to load")
                if not os.path.exists(embedding_path):
                    raise ValueError(f"Embedding file not found: {embedding_path}")

                container_embedding_path = self.get_container_path(embedding_path)
            elif self.save_embedding_radio.isChecked():
                embedding_path = self.embedding_path_edit.text().strip()

                if not embedding_path:
                    raise ValueError("Please specify a path to save the embedding")

                # Ensure the directory exists
                embedding_dir = os.path.dirname(embedding_path)

                if not os.path.exists(embedding_dir):
                    os.makedirs(embedding_dir, exist_ok=True)

                container_embedding_path = self.get_container_path(embedding_path)
                save_embeddings = True

            container_image_path = self.get_container_path(image_path)
            self.iface.messageBar().pushMessage('Info', f"Using image path: {container_image_path}", level=Qgis.Info, duration=5)
            payload = {
                "image_path": container_image_path,
                "embedding_path": container_embedding_path,
                "prompts": prompts,
                "save_embeddings": save_embeddings
            }

            # add the model path to the payload if not empty
            self.model_path = self.model_combo.currentText().strip()

            if self.model_path:
                payload["model_path"] = self.model_path
                payload["model_type"] = "sam" if self.is_sam_model() else "segment"

            # Show payload in message bar
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
                predict_url = f"{self.server_url}/predict"

                response = requests.post(predict_url, json=payload, timeout=6000000)

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

                        if not response_json:
                            raise ValueError("Empty response from server")

                        if 'features' not in response_json:
                            raise ValueError("Response missing 'features' field")

                        features = response_json['features']
                        feature_crs = response_json.get('crs', None)

                        if not features:
                            self.iface.messageBar().pushMessage("Warning", "No predictions returned from server", level=Qgis.Warning, duration=3)
                            return

                        self.add_features_to_layer(features, "predictions", crs=feature_crs) # adds the predictions as a layer

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
                embeddings_dir = os.path.join(self.data_dir, 'embeddings') if os.path.exists(os.path.join(self.data_dir, 'embeddings')) else self.data_dir
                file_path, _ = QFileDialog.getOpenFileName(None, "Select Embedding File", embeddings_dir, "Embedding Files (*.pt);;All Files (*.*)")
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
                    self.canvas.setMapTool(self.point_tool)
                elif draw_type == "Box":
                    self.canvas.setMapTool(self.box_tool)
                else:
                    self.canvas.unsetMapTool(self.point_tool)
                    self.canvas.unsetMapTool(self.box_tool)
            else:
                self.canvas.unsetMapTool(self.point_tool)
                self.canvas.unsetMapTool(self.box_tool)
        except Exception as e:
            self.logger.error(f"Error in draw type change: {str(e)}")

    def get_container_path(self, host_path):
        """Convert host path to container path if within data_dir."""
        
        if host_path and host_path.startswith(self.data_dir) and self.docker_mode_button.isChecked():
            relative_path = os.path.relpath(host_path, self.data_dir)
            return os.path.join('/usr/src/app/data', relative_path)
        
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
            self.temp_prompts_geojson = os.path.join(self.tmp_dir, f'prompts_{timestamp}.geojson')
            self.temp_predictions_geojson = os.path.join(self.tmp_dir, f'predictions_{timestamp}.geojson')

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
            if index > 0: # 0th index is "Select a layer..."
                layer_id = self.layer_dropdown.itemData(index)
                selected_layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None

                if not selected_layer:
                    return

                # Get image crs and extent
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

                self.image_path.setText(selected_layer.source())
                self.create_prediction_layers()

                # Check for existing embedding
                layer_source = selected_layer.source()

                image_name = os.path.splitext(os.path.basename(layer_source))[0]
                self.update_embeddings(image_name)

        except Exception as e:
            self.logger.error(f"Error handling layer selection: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle layer selection: {str(e)}")

    def cleanup_docker(self):
        """Clean up Docker resources when unloading plugin"""
        try:
            if self.sudo_password:
                compose_path = os.path.join(self.plugin_dir, 'docker-compose.yml')
                cmd = f'echo "{self.sudo_password}" | sudo -S docker-compose -p {self.project_name} -f "{compose_path}" down'
                subprocess.run(['bash', '-c', cmd], check=True)
        except Exception as e:
            self.logger.error(f"Error cleaning up Docker: {str(e)}")

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
            self.rubber_band.reset()
            self.temp_rubber_band.reset()
            # Reset start point for box drawing
            self.start_point = None

        except Exception as e:
            self.logger.error(f"Error cleaning up previous session: {str(e)}")
            raise

    def unload(self):
        """Cleanup when unloading the plugin"""

        try:
            self.cleanup_previous_session() # cleans up temporary files and layers

            # Remove the plugin menu item and icon
            if self.toolbar:
                self.toolbar.deleteLater()

            for action in self.actions:
                self.iface.removePluginMenu("Easy Earth", action)
                self.iface.removeToolBarIcon(action)

            self.cleanup_docker() # cleans up Docker resources

            self.sudo_password = None # clears sudo password

            # Stop the status check timer
            if hasattr(self, 'status_timer'):
                self.status_timer.stop()
                del self.status_timer

            self.clear_points()

            # Remove the plugin UI elements
            if self.dock_widget:
                self.iface.removeDockWidget(self.dock_widget)

            # Clean up any other resources
            if hasattr(self, 'point_layer') and self.point_layer:
                QgsProject.instance().removeMapLayer(self.point_layer.id())

            if hasattr(self, 'undo_shortcut') and self.undo_shortcut:
                self.undo_shortcut.setParent(None)
    
            # Remove temporary drawn features layer
            if hasattr(self, 'drawn_layer') and self.drawn_layer:
                QgsProject.instance().removeMapLayer(self.drawn_layer.id())

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
