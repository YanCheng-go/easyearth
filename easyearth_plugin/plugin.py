"""Entry point for the QGIS plugin. Handles plugin registration, menu/toolbar actions, and high-level coordination."""

from datetime import datetime
from qgis.PyQt.QtWidgets import (QAction, QDockWidget, QPushButton, QVBoxLayout,
                                QWidget, QMessageBox, QLabel, QHBoxLayout,
                                QLineEdit, QFileDialog, QComboBox, QGroupBox, QShortcut, QProgressBar, QCheckBox, QButtonGroup, QRadioButton, QApplication, QScrollArea)
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QIcon, QKeySequence, QColor
from qgis.core import (QgsVectorLayer, QgsGeometry, QgsRectangle,
                      QgsPointXY, QgsProject,
                      QgsWkbTypes, QgsRasterLayer, Qgis, QgsLayerTreeGroup, QgsCategorizedSymbolRenderer,
                      QgsRendererCategory, QgsMarkerSymbol, QgsFillSymbol, QgsCoordinateTransform, QgsSingleSymbolRenderer)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from .core import BoxMapTool, setup_logger, map_id, create_point_box, EnvManager
import json
import logging
import os
import platform
import requests
import shutil
import subprocess
import time
import traceback
import urllib.request
import zipfile

class EasyEarthPlugin:
    def __init__(self, iface):
        self.iface = iface # QGIS interface instance
        self.logger = logging.getLogger("easyearth_plugin") # global logger for the plugin

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
        self.server_url = f"http://0.0.0.0:3781/easyearth"  # Base URL for the server
        self.docker_running = False
        self.server_running = False
        self.action = None
        self.dock_widget = None
        self.point_layer = None
        self.total_steps = 0
        self.current_step = 0
        self.temp_rubber_band = None
        self.start_point = None
        self.drawn_features = []
        self.drawn_layer = None

        # Directories
        self.base_dir = '' # data directory for storing images and embeddings
        self.images_dir = '' # directory for storing images
        self.embeddings_dir = '' # directory for storing embeddings
        self.predictions_dir = '' # directory for storing predictions
        self.tmp_dir = '' # temporary directory for storing temporary files
        self.logs_dir = '' # logs directory for storing logs

        if os.name == "nt" or platform.system().lower().startswith("win"):
            self.cache_dir = os.path.join(os.environ.get("USERPROFILE", ""), ".cache", "easyearth", "models")
        else:
            self.cache_dir = os.path.join(os.environ.get("HOME", ""), ".cache", "easyearth", "models")
            
        self.model_path = None
        self.model_type = None
        self.prompt_count = {} # for generating unique IDs
        self.prediction_count = {} # for generating unique IDs
        self.prompts_geojson = {} # stores prompts in GeoJSON format
        self.predictions_geojson = {} # stores predictions in GeoJSON format
        self.temp_prompts_geojson = None # temporary file for storing prompts
        self.temp_predictions_geojson = None
        self.last_pred_time = {}  # timestamp when the real-time prediction is unchecked. or the last batch prediction was done
        self.prompts_layer = {}
        self.predictions_layer = {}
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

        # initialize image crs and extent
        self.raster_crs = None
        self.raster_extent = None
        self.raster_width = None
        self.raster_height = None
        self.project_crs = QgsProject.instance().crs()
        self.selected_layer = None  # currently selected raster layer

        QgsProject.instance().crsChanged.connect(self.on_project_crs_changed)

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

            # 1. Base folder
            base_folder_group = QGroupBox("Base Folder")
            base_folder_layout = QHBoxLayout()
            self.base_folder = QLineEdit('')
            self.base_folder.setPlaceholderText("No folder selected")
            self.base_folder.setReadOnly(True)
            self.base_folder_button = QPushButton("Select folder")
            self.base_folder_button.clicked.connect(self.select_base_folder)
            base_folder_layout.addWidget(self.base_folder)
            base_folder_layout.addWidget(self.base_folder_button)
            base_folder_group.setLayout(base_folder_layout)
            main_layout.addWidget(base_folder_group)

            # 2. Run mode
            self.run_mode_group = QGroupBox("Run Mode")
            run_mode_layout = QVBoxLayout()
            run_mode_info_label = QLabel('You can launch the plugin server either by using Docker if you have it installed or running the server locally.&nbsp;Local mode is required for making use of GPU.')
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
            self.run_mode_group.setLayout(run_mode_layout)
            main_layout.addWidget(self.run_mode_group)
            self.run_mode_group.hide() # hide by default, will show when base folder is selected

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
            self.toggle_server_button = QPushButton("")
            self.toggle_server_button.clicked.connect(self.run_or_stop_container)
            self.toggle_server_button.hide()
            service_layout.addWidget(self.toggle_server_button)

            # API Information
            api_layout = QVBoxLayout()
            api_label = QLabel("API Endpoints:")
            api_label.setStyleSheet("font-weight: bold;")
            self.api_info = QLabel(f"Base URL: {self.server_url}\n"
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

            self.model_dropdown = QComboBox()
            self.model_dropdown.setEditable(True)
            self.model_dropdown.addItems([
                "facebook/sam-vit-base",
                "facebook/sam-vit-large",
                "facebook/sam-vit-huge",
                "ultralytics/sam2.1_t",
                "ultralytics/sam2.1_s",
                "ultralytics/sam2.1_b",
                "ultralytics/sam2.1_l",
                "restor/tcd-segformer-mit-b5",
            ])
            self.model_dropdown.setEditText("facebook/sam-vit-base") # default
            self.model_dropdown.currentTextChanged.connect(self.on_model_changed)
            self.model_path = self.model_dropdown.currentText().strip()

            model_layout.addWidget(self.model_dropdown)
            self.model_group.setLayout(model_layout)
            main_layout.addWidget(self.model_group)

            # 5. Image Source Group
            self.image_group = QGroupBox("Image Source")
            self.image_group.hide()  # Hide by default, will show when model is selected
            image_layout = QVBoxLayout()

            # Image source selection
            source_layout = QHBoxLayout()
            source_label = QLabel("Source:")
            self.source_dropdown = QComboBox()
            self.source_dropdown.addItems(["File", "Layer", "Link"])
            self.source_dropdown.currentTextChanged.connect(self.on_image_source_changed)
            source_layout.addWidget(source_label)
            source_layout.addWidget(self.source_dropdown)
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
            file_layout.addWidget(self.image_download_progress_bar)

            self.downloading_progress_status = QLabel()
            self.downloading_progress_status.setWordWrap(True)
            self.downloading_progress_status.hide()
            file_layout.addWidget(self.downloading_progress_status)

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

            # Update the layer (raster) list in the combo box whenever a layer is added or removed
            QgsProject.instance().layersAdded.connect(self.update_layer_dropdown)
            QgsProject.instance().layersRemoved.connect(self.update_layer_dropdown)
            # QgsApplication.instance().aboutToQuit.connect(self.cleanup_docker) # connect to QGIS quit signal

            # Start periodic server status check
            self.status_timer = QTimer()
            self.status_timer.timeout.connect(self.check_server_status)
            self.status_timer.start(5000)  # Check every 5 seconds

            self.logger.debug("Finished initGui setup")
        except Exception as e:
            self.logger.error(f"Error in initGui: {str(e)}")
            self.logger.exception("Full traceback:")

    def get_image_name(self):
        return os.path.basename(self.image_path.text())

    def run(self):
        """Run method that loads and starts the plugin"""
        if self.dock_widget.isVisible():
            self.dock_widget.hide()
        else:
            self.dock_widget.show()

    def check_server_status(self):
        """Check if the server is running by pinging it"""

        try:
            response = requests.get(f"{self.server_url}/ping", timeout=2)

            if response.status_code == 200:
                self.server_status.setText("Online")
                self.server_status.setStyleSheet("color: green;")
                self.server_running = True
                self.docker_running = True
                self.toggle_server_button.show()
                self.toggle_server_button.setText("Stop server")

                # check GPU message in the response
                if 'device' in response.json():
                    gpu_message = response.json()['device']
                    self.server_status.setText(f"Online - Device: {gpu_message}") # adds GPU message to the server status label
                else:
                    self.iface.messageBar().pushMessage("No device info available", level=Qgis.Info)
                    self.server_status.setText(f"Online - Device: Info not available") # adds GPU message to the server status label
                if self.base_dir and (self.docker_mode_button.isChecked() or self.local_mode_button.isChecked()):
                    self.model_group.show()  # Show model selection group when server is online
                    self.image_group.show()  # Show image source group when server is online
            else:
                self.server_status.setText("Error")
                self.server_status.setStyleSheet("color: red;")
                self.server_running = False
                self.docker_running = False
                self.toggle_server_button.setText("Start server")
        except requests.exceptions.RequestException:
            self.server_status.setText("Offline")
            self.server_status.setStyleSheet("color: red;")
            self.server_running = False
            self.docker_running = False
            self.toggle_server_button.show()
            self.toggle_server_button.setText("Start server")

    def select_base_folder(self):
        """Select the base folder for storing data.
        If an existing is running when opening QGIS, it uses the parent directory of the existing base directory.
        If not, it opens a dialog to select a folder.
        """
        folder = QFileDialog.getExistingDirectory(self.dock_widget, "Select location for base folder", '', QFileDialog.ShowDirsOnly) # opens a dialog to select a folder

        if folder: # if a folder is selected
            self.base_dir = os.path.join(folder, 'easyearth_base')
            self.images_dir = os.path.join(self.base_dir, 'images')
            self.embeddings_dir = os.path.join(self.base_dir, 'embeddings')
            self.predictions_dir = os.path.join(self.base_dir, 'predictions')
            self.tmp_dir = os.path.join(self.base_dir, 'tmp')
            self.logs_dir = os.path.join(self.base_dir, 'logs')
            self.base_folder.setText(self.base_dir)
            self.iface.messageBar().pushMessage(f"Base folder set to {self.base_dir}", level=Qgis.Info)
            self.run_mode_group.show() # shows run mode group when base folder is selected
            
            os.makedirs(self.images_dir, exist_ok=True)  # creates the images directory if it doesn't exist
            os.makedirs(self.embeddings_dir, exist_ok=True)  # creates the embeddings directory if it doesn't exist
            os.makedirs(self.predictions_dir, exist_ok=True)  # creates the predictions directory if it doesn't exist
            os.makedirs(self.tmp_dir, exist_ok=True)  # creates the tmp directory if it doesn't exist
            os.makedirs(self.logs_dir, exist_ok=True)  # creates the logs directory if it doesn't exist
            
            os.environ['BASE_DIR'] = self.base_dir

    def run_mode_selected(self, mode):
        """Handle run mode selection (Docker or Local)"""
        self.server_group.show()  # Show server group when a mode is selected

        if mode == 'docker':
            self.local_mode_button.setChecked(False)
            self.docker_mode = True
        elif mode == 'local':
            self.docker_mode_button.setChecked(False)
            self.docker_mode = False

    def start_server(self):
        if self.docker_mode_button.isChecked():
            linux_gpu_flags = " --runtime nvidia" if platform.system().lower() == "linux" else ""  # adds GPU support if available and on Linux
            gpu_flags = " --gpus all" if platform.system().lower() != "darwin" else ""  # adds GPU support if available and not on macOS
            self.iface.messageBar().pushMessage('Removing the docker container if it already exists', level=Qgis.Info)
            QApplication.processEvents()
            subprocess.run(f"{self.docker_path} rm -f easyearth 2>/dev/null || true", capture_output=True, text=True, shell=True)  # removes the container if it already exists
            self.iface.messageBar().pushMessage('Pulling the latest image from Docker Hub', level=Qgis.Info)
            QApplication.processEvents()
            warning_box = QMessageBox()
            warning_box.setIcon(QMessageBox.Warning)
            warning_box.setWindowTitle("Update Docker Image")
            warning_box.setTextFormat(Qt.RichText)
            warning_box.setText("Downloading or updating Docker image from Docker Hub.&nbsp;This may take a while for the first time,&nbsp;please wait...")
            warning_box.show()
            subprocess.run(f"{self.docker_path} pull {self.docker_hub_image_name}", capture_output=True, text=True, shell=True)  # removes the container if it already exists
            self.iface.messageBar().pushMessage('Starting the Docker container', level=Qgis.Info)
            QApplication.processEvents()
            docker_run_cmd = (f"{self.docker_path} run{linux_gpu_flags}{gpu_flags} -d --name easyearth -p 3781:3781 " # runs the container in detached mode and maps port 3781
                              f"-v \"{self.base_dir}\":/usr/src/app/easyearth_base " # mounts the base directory in the container
                              f"-v \"{self.cache_dir}\":/usr/src/app/.cache/models " # mounts the cache directory in the container
                              f"{self.docker_hub_image_name}")
            result = subprocess.run(docker_run_cmd, capture_output=True, text=True, shell=True, timeout=1800)
            self.iface.messageBar().pushMessage(f"Starting server...\nRunning command: {result}", level=Qgis.Info)
            
            if result.returncode == 0:
                self.docker_running = True
                self.iface.messageBar().pushMessage("Docker container started successfully.", level=Qgis.Success)

        if self.local_mode_button.isChecked():
            # Download server code
            repo_url = "https://github.com/YanCheng-go/easyearth/archive/refs/heads/master.zip"
            zipped_repo_path = os.path.join(self.base_dir, 'easyearth-master.zip')
            repo_path = os.path.join(self.base_dir, 'easyearth-master')
            easyearth_folder_path = os.path.join(self.base_dir, 'easyearth')

            if not os.path.exists(easyearth_folder_path):
                self.iface.messageBar().pushMessage(f"Downloading easyearth repo from {repo_url} to {zipped_repo_path}", level=Qgis.Info)
                QApplication.processEvents()
                urllib.request.urlretrieve(repo_url, zipped_repo_path)
                
                self.iface.messageBar().pushMessage(f"Unzipping repo to {repo_path}", level=Qgis.Info)
                QApplication.processEvents()

                with zipfile.ZipFile(zipped_repo_path, 'r') as zip_ref:
                    zip_ref.extractall(self.base_dir)

                self.iface.messageBar().pushMessage(f"Moving easyearth folder out of repo to {easyearth_folder_path}", level=Qgis.Info)
                QApplication.processEvents()
                shutil.move(os.path.join(repo_path, "easyearth"), easyearth_folder_path)
                shutil.rmtree(repo_path)
                os.remove(zipped_repo_path)

            # Download env
            env_path = os.path.join(self.base_dir, 'easyearth_env')

            if not os.path.exists(env_path):
                QMessageBox.warning(None, "Local Python Environment Not Found", "Downloading EasyEarth Python environment. This may take a while,&nbsp;please wait...")
                self.iface.messageBar().pushMessage(f"Downloading EasyEarth Python environment for {platform.system().lower()} system",level=Qgis.Info)

                if platform.system().lower() == 'darwin':  # macOS
                    env_url = 'https://github.com/YanCheng-go/easyearth/releases/download/env-v3/easyearth_env.tar.gz'
                    zipped_env_path = os.path.join(self.base_dir, 'easyearth_env.tar.gz')
                    self.iface.messageBar().pushMessage(f"Downloading environment from {env_url} to {zipped_env_path}", level=Qgis.Info)
                    QApplication.processEvents()
                    urllib.request.urlretrieve(env_url, zipped_env_path)
                    self.iface.messageBar().pushMessage(f"Unzipping environment to {env_path}", level=Qgis.Info)
                    QApplication.processEvents()
                    subprocess.run(f'tar -xzf \"{zipped_env_path}\" -C \"{self.base_dir}\"', capture_output=True, text=True, shell=True)  # unzips the environment tar.gz file
                    os.remove(zipped_env_path)  # remove the zip file after extraction
                else:
                    EnvManager(self.iface, self.logs_dir, self.plugin_dir).download_linux_env() # Use EnvManager to download (internally calls download_linux_env.sh)
                
                self.iface.messageBar().pushMessage(f"Unzipped environment to {env_path}", level=Qgis.Info)

            self.local_server_log_file = open(f"{self.logs_dir}/launch_server_local.log", "w")  # log file for the local server launch
            self.iface.messageBar().pushMessage(f"Starting local server...", level=Qgis.Info)
            result = subprocess.Popen(f'chmod +x \"{self.plugin_dir}\"/launch_server_local.sh && \"{self.plugin_dir}\"/launch_server_local.sh',
                                    shell=True,
                                    stdout=self.local_server_log_file,  # redirects stdout to a log file
                                    stderr=subprocess.STDOUT,  # redirects stderr to the same log file
                                    text=True,              # decodes output as text, not bytes
                                    start_new_session=True)  # detaches from QGIS
            
            if result:
                self.iface.messageBar().pushMessage(f"Local server started successfully. Check logs {self.local_server_log_file} for details.", level=Qgis.Success)

    def stop_server(self):
        if self.docker_mode_button.isChecked():
            result = subprocess.run(f"{self.docker_path} stop easyearth && {self.docker_path} rm easyearth", capture_output=True, text=True, shell=True)
            self.docker_hub_process = None
            self.docker_running = False
        else:
            result = subprocess.run('kill $(lsof -t -i:3781)', capture_output=True, text=True, shell=True, timeout=1800) # kills the process running on port 3781

        self.iface.messageBar().pushMessage(f"Stopping server with command: {result}", level=Qgis.Info)

    def run_or_stop_container(self):
        if not self.docker_running: # if the docker container is not running, start it
            self.base_folder.setReadOnly(True)
            self.base_folder_button.setEnabled(False)
            self.start_server()
        else: # if the container is running, stop it
            self.stop_server()
            self.base_folder.setReadOnly(False)
            self.base_folder_button.setEnabled(True)
            self.toggle_server_button.setText("Start server")

            if self.local_mode_button.isChecked():
                self.toggle_server_button.hide()

    def on_image_source_changed(self, text):
        """Handle image source selection change"""

        try:
            is_sam = self.is_sam_model()  # check if the selected model is a SAM model
            if text == "File":
                self.image_path.show()
                self.image_path.setReadOnly(True)
                self.browse_button.show()
                self.layer_dropdown.hide()
                self.download_button.hide()
                self.image_path.clear()
                self.image_path.setPlaceholderText("No image selected")
                self.initialize_embedding_path()
                self.deactivate_embedding_section() if not is_sam else None
            elif text == "Layer":
                self.image_path.hide()
                self.browse_button.hide()
                self.download_button.hide()
                self.layer_dropdown.show()
                self.update_layer_dropdown()
                self.embedding_group.setVisible(is_sam) # show embedding section if SAM model is selected
            elif text == "Link":
                self.image_path.show()
                self.image_path.setReadOnly(False)
                self.browse_button.hide()
                self.download_button.show()
                self.layer_dropdown.hide()
                self.image_path.setPlaceholderText("Enter image URL (http/https...)")
                self.image_path.clear()
                self.initialize_embedding_path()
                self.deactivate_embedding_section() if not is_sam else None

            # self.cleanup_previous_session() # clears any existing layers

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
            save_path = os.path.join(self.base_dir, local_filename)
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
            self.source_dropdown.setCurrentText("File")
            self.image_path.setText(save_path)
            self.load_image()
        except Exception as e:
            self.logger.error(f"Error downloading image: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to download image: {str(e)}")

    def on_project_crs_changed(self):
        """Update the cached project CRS when the project CRS changes."""

        self.project_crs = QgsProject.instance().crs()
        self.iface.messageBar().pushMessage(f"Project CRS changed to: {self.project_crs.authid()}", level=Qgis.Info, duration=5)

    def on_realtime_checkbox_changed(self):
        """Enable or disable the prediction button based on real-time mode."""
        self.predict_button.setEnabled(not self.realtime_checkbox.isChecked()) # if real-time mode is checked, disable the prediction button, vice versa

        # If real-time mode is unchecked, reset the last prediction time
        if not self.realtime_checkbox.isChecked():
            self.last_pred_time[self.get_image_name()] = time.time()

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
        is_sam = self.model_path.startswith("facebook/sam-") or self.model_path.startswith("ultralytics/sam2")
        return is_sam

    def is_sam2_model(self):
        """Check if the selected model is a SAM2 model."""
        return self.model_path.startswith("ultralytics/sam2")

    def on_model_changed(self, text=None):
        """1. Enable drawing and embedding only if a SAM model is selected.
           2. Update the embedding path according to model selection."""

        if text is not None:
            self.model_path = text.strip()
        else:
            self.model_path = self.model_dropdown.currentText().strip()

        is_sam = self.is_sam_model()

        # # Drawing section
        # self.draw_button.setEnabled(is_sam)
        # self.draw_type_dropdown.setEnabled(is_sam)
        # self.realtime_checkbox.setEnabled(is_sam)

        # if not is_sam:
        #     self.draw_button.setChecked(False)
        #     self.draw_button.setText("Start drawing")

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
            embedding_dir = os.path.join(self.base_dir, 'embeddings')
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
                    self.embedding_path_edit.setText(embedding_path)

                    self.iface.messageBar().pushMessage(
                        f"Will use existing embedding for {image_name}.",
                        level=Qgis.Info)
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

    def on_image_selected(self):
        """Handle image selection from file."""

        for group in QgsProject.instance().layerTreeRoot().children():
            for layer in group.children():
                if layer.name() == self.get_image_name():
                    self.selected_layer = layer.layer()

        self.iface.setActiveLayer(self.selected_layer) # sets the selected layer as the active layer
        self.iface.messageBar().pushMessage(f"Selected layer {self.selected_layer.name()}", level=Qgis.Info)
        self.raster_extent, self.raster_width, self.raster_height, self.raster_crs = self.get_current_raster_info(self.selected_layer)
        msg = (
            f"Extent: X min: {self.raster_extent.xMinimum()}, X max: {self.raster_extent.xMaximum()}, "
            f"Y min: {self.raster_extent.yMinimum()}, Y max: {self.raster_extent.yMaximum()}; "
            f"Width: {self.raster_width}; "
            f"Height: {self.raster_height}; "
            f"CRS: {self.raster_crs.authid()}"
        )
        self.iface.messageBar().pushMessage(msg, level=Qgis.Info,)
        
        if self.selected_layer.crs() != self.project_crs:
            QgsProject.instance().setCrs(self.selected_layer.crs())  # Set the layer CRS to match the project CRS
        
        extent = self.selected_layer.extent()

        if not extent.isEmpty():
            # Add small buffer around the layer (5%)
            width = extent.width()
            height = extent.height()
            
            if width > 0 and height > 0:
                buffer_x = width * 0.05
                buffer_y = height * 0.05
                
                extent.setXMinimum(extent.xMinimum() - buffer_x)
                extent.setXMaximum(extent.xMaximum() + buffer_x)
                extent.setYMinimum(extent.yMinimum() - buffer_y)
                extent.setYMaximum(extent.yMaximum() + buffer_y)
            
            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()
        
        # Reorder the group to be at the top
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(self.selected_layer.name())
        root.insertChildNode(0, group.clone())  # inserts the group at the top of the layer tree
        group.parent().removeChildNode(group) # removes the original group
        self.iface.mapCanvas().refresh()
        
    def browse_image(self):
        """Open file dialog for image selection"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(self.dock_widget,
                                                       "Select image",
                                                       self.images_dir,
                                                       "Image Files (*.png *.jpg *.jpeg *.tif *.tiff *.JPG *.JPEG *.PNG *.TIF *.TIFF);;All Files (*.*)")

            if file_path:
                # Verify the file is within data_dir
                if not os.path.commonpath([file_path]).startswith(os.path.commonpath([self.base_dir])):
                    QMessageBox.warning(None, "Invalid Location", f"Please select an image from within the data directory:\n{self.base_dir}")
                    return

                self.image_path.setText(file_path)
                self.load_image() # loads the image to canvas

        except Exception as e:
            self.logger.error(f"Error browsing image: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to browse image: {str(e)}")

    def check_group_exists(self, group_name):
        """Checks if a group with the given name already exists in the layer tree."""

        root = QgsProject.instance().layerTreeRoot()

        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup) and child.name() == group_name:
                return True
            
        return False

    def load_image(self):
        """Load the selected image, create prediction layers, and check for existing embeddings"""
        try:
            # Get the image path
            image_path = self.image_path.text()
            is_sam = self.is_sam_model()  # check if the selected model is a SAM model

            if not image_path:
                return

            layer_name = os.path.basename(image_path)
            raster_layer = QgsRasterLayer(image_path, layer_name) # loads the image as a raster layer

            if not raster_layer.isValid():
                QMessageBox.warning(None, "Error", "Invalid raster layer")
                return

            instance = QgsProject.instance()

            if len(instance.mapLayersByName(raster_layer.name())) == 0:
                instance.addMapLayer(raster_layer, False) # False = don't auto-add to legend
                root = instance.layerTreeRoot()
                group = root.insertGroup(0, layer_name)
                group.addLayer(raster_layer) # adds the layer to the group
            
            self.on_image_selected()
            self.create_prediction_layers()

            if is_sam:
                self.update_embeddings()

            self.embedding_group.setVisible(is_sam)  # Show embedding section if SAM model is selected
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

    # TODO: use this generic function to convert any geometry to pixel coordinates
    def map_geom_to_pixel_coords(self, box_geom):
        """
        Convert a geometry in map coordinates to pixel coordinates (top-left (0,0)).
        Args:
            box_geom (QgsGeometry): Geometry in map coordinates (like from create_point_box).
        Returns:
            tuple: (xmin, ymin, xmax, ymax) in pixel coordinates.
        """

        raster_extent, raster_width, raster_height = self.raster_extent, self.raster_width, self.raster_height

        bbox = box_geom.boundingBox()

        # Ensure bbox is within raster extent
        if not raster_extent.contains(bbox):
            QMessageBox.critical(None, "Error", "Bounding box is outside the raster extent. Please ensure the geometry is within the raster bounds.")
            return None

        # Map extent
        xmin_map, xmax_map = raster_extent.xMinimum(), raster_extent.xMaximum()
        ymin_map, ymax_map = raster_extent.yMinimum(), raster_extent.yMaximum()

        # Map to pixel conversion (image coords: (0,0) at top-left)
        pixel_xmin = int((bbox.xMinimum() - xmin_map) * raster_width / raster_extent.width())
        pixel_xmax = int((bbox.xMaximum() - xmin_map) * raster_width / raster_extent.width())
        pixel_ymin = int((ymax_map - bbox.yMaximum()) * raster_height / raster_extent.height())
        pixel_ymax = int((ymax_map - bbox.yMinimum()) * raster_height / raster_extent.height())

        # Clamp to image boundaries
        pixel_xmin = max(0, min(pixel_xmin, raster_width - 1))
        pixel_xmax = max(0, min(pixel_xmax, raster_width - 1))
        pixel_ymin = max(0, min(pixel_ymin, raster_height - 1))
        pixel_ymax = max(0, min(pixel_ymax, raster_height - 1))

        return (pixel_xmin, pixel_ymin, pixel_xmax, pixel_ymax)

    def show_aoi_on_map(self, geom):
        """Display the Area of Interest (AOI) on the map canvas."""
        # Check if self.aoi_rubber_band already exists; if not, create it
        if not hasattr(self, 'aoi_rubber_band') or self.aoi_rubber_band is None:
            self.aoi_rubber_band = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
            self.aoi_rubber_band.setColor(QColor(0, 0, 255, 100))  # Blue, semi-transparent
            self.aoi_rubber_band.setWidth(2)

        # Clear previous geometry and set the new one
        self.aoi_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
        self.aoi_rubber_band.addGeometry(geom, None)
        self.aoi_rubber_band.show()  # Show the rubber band on the map canvas

        # # Zoom to extent
        # extent = geom.boundingBox()
        # self.canvas.setExtent(extent)
        # self.canvas.refresh()

    def clear_aoi(self):
        """Clear the Area of Interest (AOI) from the map canvas."""
        if hasattr(self, 'aoi_rubber_band') and self.aoi_rubber_band is not None:
            self.aoi_rubber_band.reset(QgsWkbTypes.PolygonGeometry)
            self.aoi_rubber_band.hide()

    def on_point_drawn(self, point, button):
        """Handle canvas clicks for drawing points or boxes
        Args:
            point (QgsPointXY): The clicked point in map coordinates
            button (Qt.MouseButton): The mouse button that was clicked
        """
        try:            
            if not self.draw_button.isChecked() or button != Qt.LeftButton:
                return None
            is_sam = self.is_sam_model()
            draw_type = self.draw_type_dropdown.currentText()
            extent, width, height, raster_crs = self.raster_extent, self.raster_width, self.raster_height, self.raster_crs

            # # Transform point to raster CRS if needed
            # if self.project_crs != raster_crs and raster_crs is not None:
            #     transform = QgsCoordinateTransform(self.project_crs, raster_crs, QgsProject.instance())
            #     point = transform.transform(point)

            prompt = []
            aoi_feature = None
            point_feature = None

            if draw_type == "Point":
                # Check if the point is within the raster extent
                if not extent.contains(point):
                    QMessageBox.critical(None, "Error", "Point coordinates are outside the image bounds. Please make sure you selected the right image and draw a valid point within the image.")
                    return None
                # Calculate pixel coordinates
                px = int((point.x() - extent.xMinimum()) * width / extent.width())
                py = int((extent.yMaximum() - point.y()) * height / extent.height())

                # Ensure coordinates are within image bounds
                px = max(0, min(px, width - 1))
                py = max(0, min(py, height - 1))

                if self.get_image_name() not in self.prompt_count.keys():
                    # self.iface.messageBar().pushMessage(f'No prompts found for {self.get_image_name()}', level=Qgis.Info)
                    self.prompt_count[self.get_image_name()] = 0

                self.iface.messageBar().pushMessage(f"Image name: {self.get_image_name()}\n"
                                                    f"Map coordinates: ({point.x():.2f}, {point.y():.2f})\n"
                                                    f"Pixel coordinates: ({px}, {py})\n",
                                                    level=Qgis.Info)

                # Create prompt feature
                point_feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [point.x(), point.y()]
                    },
                    "properties": {
                        "id": self.prompt_count[self.get_image_name()],
                        "type": "Point",
                        "pixel_x": px,
                        "pixel_y": py,
                        "pixel_width": 0,
                        "pixel_height": 0,
                    }
                }

                point_feature["properties"]["timestamp"] = time.time() # adds timestamp to prompt feature

                if is_sam:
                    prompt = [{'type': 'Point', 'data': {"points": [[px, py]]}}]
                    aoi_feature = None
                else:
                    # If not SAM model, create a box around the point, with a buffer of 500 pixels or 500 meters
                    box_geom = create_point_box(point, self.selected_layer)
                    self.show_aoi_on_map(box_geom)
                    aoi_feature = self.map_geom_to_pixel_coords(box_geom)
                    prompt = []

            self.add_features_to_layer([point_feature], "prompts")  # adds point to layer
            self.prompt_count[self.get_image_name()] += 1  # increments prompt counter

            if self.realtime_checkbox.isChecked():
                self.get_prediction(prompt, [aoi_feature])
            return point

        except Exception as e:
            self.logger.error(f"Error handling draw click: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle drawing: {str(e)}")
            return None

    def on_box_drawn(self, box_geom, start_point, end_point):
        """Handle box drawing completion
        Args:
            box_geom (QgsGeometry): The drawn box geometry
            start_point (QgsPointXY): The starting point of the box
            end_point (QgsPointXY): The ending point of the box
        """

        # Check if the box is valid
        if not box_geom.isGeosValid():
            self.iface.messageBar().pushMessage("Invalid box geometry", level=Qgis.Critical)
            return

        extent, width, height, raster_crs = self.raster_extent, self.raster_width, self.raster_height, self.raster_crs # gets raster layer information

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

        # check if within image bounds
        if not extent.contains(start_point) or not extent.contains(end_point):
            QMessageBox.critical(None, "Error", "Box coordinates are outside the image bounds. Please make sure you selected the right image and draw a valid box within the image.")
            return

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

        self.iface.messageBar().pushMessage(
            f"Box coordinates: ({pixel_x}, {pixel_y}, {pixel_x + pixel_width}, {pixel_y + pixel_height})",
            level=Qgis.Info
        )

        if self.get_image_name() not in self.prompt_count.keys():
            self.prompt_count[self.get_image_name()] = 0

        # Create prompt feature
        feature = {
            "type": "Feature",
            "geometry": json.loads(box_geom.asJson()),
            "properties": {
                "id": self.prompt_count[self.get_image_name()],
                "type": "Box",
                "pixel_x": pixel_x,
                "pixel_y": pixel_y,
                "pixel_width": pixel_width,
                "pixel_height": pixel_height,
                "timestamp": time.time()
            }
        }

        self.add_features_to_layer([feature], "prompts") # adds prompt feature to layer
        self.prompt_count[self.get_image_name()] += 1 # increments prompt counter

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

        aoi_feature = (pixel_x, pixel_y, pixel_x + pixel_width, pixel_y + pixel_height) # creates a tuple with 4 coordinates (x_min, y_min, x_max, y_max)

        if not self.is_sam_model():
            prompt = []  # if not SAM model, set prompt to empty list

        # Send prediction request if realtime checkbox is checked
        if self.realtime_checkbox.isChecked():
            self.get_prediction(prompt, [aoi_feature]) # sends prediction request if real-time mode is checked

        return box_geom

    def undo_last_drawing(self):
        """Undo the last drawing action by removing the last point or box"""

        if self.prompt_count[self.get_image_name()] == 0:
            self.iface.messageBar().pushMessage(f'No drawings to undo for {self.get_image_name()}.', level=Qgis.Warning)
            return

        last_prompt_id = self.prompts_geojson[self.get_image_name()]['features'][-1]['properties']['id'] # gets the last prompt ID from prompts_geojson
        # self.iface.messageBar().pushMessage(f'Last prompt ID: {last_prompt_id}', level=Qgis.Info)
        # last_prediction_ID = map_id(self.prompts_geojson[self.get_image_name()]['features']) # finds the last prediction feature ID using map_id
        last_prediction_ID = dict((f['properties']['id'], i) for i, f in enumerate(self.prompts_geojson[self.get_image_name()]['features']))
        # self.iface.messageBar().pushMessage(f'Last prediction ID: {last_prediction_ID}', level=Qgis.Info)

        self.prompts_geojson[self.get_image_name()]['features'] = self.prompts_geojson[self.get_image_name()]['features'][:-1] # removes the last point from the prompts geojson
        self.prompt_count[self.get_image_name()] = self.prompt_count[self.get_image_name()] - 1 if self.prompt_count[self.get_image_name()] > 0 else 0  # decrements the prompt counter
        self.add_features_to_layer([], "prompts") # updates the prompts layer

        self.clear_aoi()

        if self.predictions_geojson:
            if self.realtime_checkbox.isChecked():
                self.predictions_geojson[self.get_image_name()]['features'] = self.predictions_geojson[self.get_image_name()]['features'][:-1] # removes the last point from the prompts geojson
                self.prediction_count[self.get_image_name()] = self.prediction_count[self.get_image_name()] - 1 if self.prediction_count[self.get_image_name()] > 0 else 0
                self.add_features_to_layer([], "predictions")
            else:
                # Get the last prediction ID from predictions_geojson
                last_prediction_index = last_prediction_ID.get(last_prompt_id, None)
                # self.iface.messageBar().pushMessage(f'Last prediction index: {last_prediction_index}', level=Qgis.Info)
                last_prediction_id = self.predictions_geojson[self.get_image_name()]['features'][last_prediction_index]['properties']['id']
                # self.iface.messageBar().pushMessage(f'Last prediction id: {last_prediction_id}', level=Qgis.Info)
                # self.iface.messageBar().pushMessage(f"{self.predictions_geojson[self.get_image_name()]['features']}", level=Qgis.Info)
                if last_prediction_id is None:
                    self.iface.messageBar().pushMessage("Error", "No matching prediction found for the last prompt.", level=Qgis.Critical, duration=3)
                    return

                self.predictions_geojson[self.get_image_name()]['features'] = [f for f in self.predictions_geojson[self.get_image_name()]['features'] if f['properties']['id'] != last_prediction_id] # removes the last prediction feature from predictions_geojson
                self.prediction_count[self.get_image_name()] = self.prediction_count[self.get_image_name()] - 1 if self.prediction_count[self.get_image_name()] > 0 else 0 # updates the feature count
                self.add_features_to_layer([], "predictions") # updates the predictions layer

    def add_features_to_layer(self, features, layer_type='prompts', crs=None, model_path=None):
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
                layer_type = 'prompts_layer'
                layer_name = f"{self.get_image_name()}_prompts"
                style_func = self.style_prompts_layer
                
                # Ensure 'type' property for styling
                for feat in features:
                    if 'properties' not in feat:
                        feat['properties'] = {}
                        
                    if 'type' not in feat['properties']:
                        geom_type = feat.get('geometry', {}).get('type', '')
                        feat['properties']['type'] = 'Point' if geom_type == 'Point' else 'Box' if geom_type == 'Polygon' else 'Unknown'

                # convert project crs to raster crs
                # transform = QgsCoordinateTransform(self.project_crs, raster_crs, QgsProject.instance())
                
                # if self.project_crs != raster_crs:
                #     self.iface.messageBar().pushMessage(f"Project CRS ({self.project_crs.authid()}) does not match raster CRS ({raster_crs.authid()}). "
                #                                         "Transforming prompts crs to match raster CRS.",
                #                                         level=Qgis.Warning,
                #                                         duration=5)
                    
                #     for feature in features:
                #         geom_json = feature.get('geometry')
                        
                #         if geom_json and geom_json['type'] == 'Polygon':
                #             map_coords = []
                            
                #             for ring in geom_json['coordinates']:
                #                 map_ring = []
                                
                #                 for map_x, map_y in ring:
                #                     point = QgsPointXY(map_x, map_y)
                #                     point = transform.transform(point)
                #                     map_ring.append(point)
                                
                #                 map_coords.append(map_ring)
                            
                #             feature['geometry']['coordinates'] = [[(p.x(), p.y()) for p in ring] for ring in map_coords]
                        
                #         if geom_json and geom_json['type'] == 'Point':
                #             map_x, map_y = geom_json['coordinates']
                #             point = QgsPointXY(map_x, map_y)
                #             point = transform.transform(point)
                #             feature['geometry']['coordinates'] = [point.x(), point.y()]

            elif layer_type == 'predictions':
                geojson_attr = 'predictions_geojson'
                temp_geojson = self.temp_predictions_geojson
                layer_type = 'predictions_layer'
                layer_name = f"{self.get_image_name()}_predictions"
                style_func = self.style_predictions_layer

                # Assign unique ids
                if self.get_image_name() not in self.prediction_count.keys():
                # if not hasattr(self, 'prediction_count'):
                    self.prediction_count[self.get_image_name()] = 0

                start_id = self.prediction_count[self.get_image_name()]
                features = [{
                    "type": "Feature",
                    "properties": {
                        "id": start_id + i,
                        "model_path": model_path,
                        # "scores": feat.get('properties', {}).get('scores', 0),  # TODO： if scores are available in the feature properties
                    },
                    "geometry": feat['geometry']
                } for i, feat in enumerate(features)]
                self.prediction_count[self.get_image_name()] += len(features)

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

                        elif geom_json and geom_json['type'] == 'MultiPolygon':
                            map_coords = []
                            for polygon in geom_json['coordinates']:  # list of polygons
                                poly_coords = []
                                for ring in polygon:  # list of rings
                                    map_ring = []
                                    for pixel_coord in ring:
                                        col, row = pixel_coord  # (x, y) = (col, row)
                                        map_x = extent.xMinimum() + (col * extent.width() / width)
                                        map_y = extent.yMaximum() - (row * extent.height() / height)
                                        point = QgsPointXY(map_x, map_y)
                                        point = transform.transform(point)
                                        map_ring.append((point.x(), point.y()))
                                    poly_coords.append(map_ring)
                                map_coords.append(poly_coords)
                            feature['geometry']['coordinates'] = map_coords

            else:
                raise ValueError("Invalid layer_type")

            # Prepare or update GeoJSON
            geojson = getattr(self, geojson_attr).get(self.get_image_name(), None)
            
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
                
            current_dict = getattr(self, geojson_attr, {})
            current_dict[self.get_image_name()] = geojson
            setattr(self, geojson_attr, current_dict)

            # Write GeoJSON file
            with open(temp_geojson, 'w') as f:
                json.dump(geojson, f)

            # Create or update layer
            layer = getattr(self, layer_type).get(self.get_image_name(), None)
            instance = QgsProject.instance()
            group = instance.layerTreeRoot().findGroup(self.get_image_name())

            if layer:
                group.removeChildNode(group.findLayer(layer.id())) # removes the layer from the group
                instance.removeMapLayer(layer.id()) # removes the layer from the project
            
            layer = QgsVectorLayer(temp_geojson, layer_name, "ogr")
            layer.setCrs(self.raster_crs)
            layer.setExtent(self.raster_extent)
            group.insertLayer(0, layer)  # inserts the layer at the top of the group
            instance.addMapLayer(layer, False) # False = don't auto-add to legend

            # if not layer:

            if not layer.isValid():
                raise ValueError("Failed to create valid vector layer")
            
            # instance.layerTreeRoot().findGroup(self.get_image_name()).insertLayer(0, layer) # adds the layer to the top of the group
            current_dict = getattr(self, layer_type, {})
            current_dict[self.get_image_name()] = layer
            setattr(self, layer_type, current_dict) # updates the layer dictionary
            # inspect = getattr(self, layer_type)[self.get_image_name()]
            # self.iface.messageBar().pushMessage(f'Layer type: {layer_type}, {inspect.name()}', level=Qgis.Info)

            # else:
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
            list of dicts with prompt data, list of tuples of AOI coordinates
        """
        try:
            prompts = []
            aoi_features = []

            if self.prompts_layer:
                for feature in self.prompts_layer[self.get_image_name()].getFeatures():
                    # self.iface.messageBar().pushMessage(f'Feature: {feature.id()}', level=Qgis.Info)
                    # Check if the feature is new
                    timestamp = feature.attribute('timestamp')

                    if self.get_image_name() not in self.last_pred_time.keys():
                        self.last_pred_time[self.get_image_name()] = 0
                    
                    # self.iface.messageBar().pushMessage(f'{timestamp}', level=Qgis.Info)

                    if timestamp is None or timestamp < self.last_pred_time[self.get_image_name()]:
                        self.iface.messageBar().pushMessage(f'continued', level=Qgis.Info)
                        continue

                    prompt_type = feature['type']

                    if prompt_type == 'Point':
                        x = feature['pixel_x']
                        y = feature['pixel_y']
                        prompts.append({'type': 'Point', 'data': {'points': [[x, y]]}}) # TODO: figure out labels for points, when used together with bounding boxes to remove part of the prediction masks

                        if not self.is_sam_model():
                            # Create a box geometry around the point
                            point = feature.geometry().asPoint()
                            box_geom = create_point_box(point, self.selected_layer)
                            self.show_aoi_on_map(box_geom) # show the AOI on the map canvas
                            one_aoi = self.map_geom_to_pixel_coords(box_geom)  # convert into pixel coordinates
                            aoi_features.append(one_aoi)

                    elif prompt_type == 'Box':
                        x1 = feature['pixel_x']
                        y1 = feature['pixel_y']
                        x2 = feature['pixel_x'] + feature['pixel_width']
                        y2 = feature['pixel_y'] + feature['pixel_height']
                        prompts.append({'type': 'Box', 'data': {'boxes': [[x1, y1, x2, y2]]}})
                        aoi_features.append((x1, y1, x2, y2))  # adds the box coordinates to AOI features
                    else:
                        self.iface.messageBar().pushMessage('Unknown prompt type', level=Qgis.Info)
                        self.logger.error(f"Unknown prompt type: {prompt_type}")
                        raise ValueError(f"Unknown prompt type: {prompt_type}")

            return prompts, aoi_features
        except Exception as e:
            tb = traceback.format_exc()
            self.iface.messageBar().pushMessage(f'tb: {tb}', level=Qgis.Info)
            return [], []

    def on_predict_button_clicked(self):
        """Run prediction: batch if prompts exist, else no-prompts prediction."""
        try:
            prompts, aoi_features = self.collect_all_prompts()  # Implement this to gather all drawn prompts
            self.iface.messageBar().pushMessage(f'prompts: {prompts}', level=Qgis.Info)
            self.iface.messageBar().pushMessage(f'aoi_features: {aoi_features}', level=Qgis.Info)
            # if there are boxes and points in the prompts, we need to run the prediction for both
            if self.is_sam_model():
                if len(prompts) == 0:
                    QMessageBox.critical(None, "Error", "No prompts found. Please draw points or boxes or use a different model.")
                    self.iface.messageBar().pushMessage("No prompts found. Please draw points or boxes.", level=Qgis.Info)
                    return
                else:
                #     # Check if there are both points and boxes
                #     has_points = any(p['type'] == 'Point' for p in prompts)
                #     has_boxes = any(p['type'] == 'Box' for p in prompts)
                    # if not (has_points and has_boxes):
                    #     # Run prediction for all prompts if only one type is present
                    #     self.get_prediction(prompts)
                    # else:
                    #     # Run prediction for points and boxes separately
                    #     self.iface.messageBar().pushMessage(
                    #         "Info",
                    #         f"Running prediction for box and point prompts separatly.",
                    #         level=Qgis.Info,
                    #         duration=3
                    #     )
                    #     points = [p for p in prompts if p['type'] == 'Point']
                    #     self.get_prediction(points)
                    #     boxes = [p for p in prompts if p['type'] == 'Box']
                    #     self.get_prediction(boxes)
                    self.get_prediction(prompts)
            else:
                # For other models, run prediction without prompts
                self.iface.messageBar().pushMessage("Running prediction without prompts.", level=Qgis.Info, duration=3)
                self.get_prediction([], aoi_features)
            
            self.last_pred_time[self.get_image_name()] = time.time()  # Update last prediction time
        except Exception as e:
            self.logger.error(f"Error running prediction: {str(e)}")
            QMessageBox.critical(None, "Error", f"Failed to run prediction: {str(e)}")

    def get_prediction(self, prompts, aoi_features=None):
        if len(prompts) == 0:
            if len(aoi_features) > 0:
                for aoi in aoi_features:
                    self.get_prediction_per_prompt(prompts, aoi_features=aoi)
            else:
                self.get_prediction_per_prompt(prompts)
        else:
            for prompt in prompts:
                self.get_prediction_per_prompt([prompt])

    def get_prediction_per_prompt(self, prompts, aoi_features=None):
        """Get prediction from SAM server and add to predictions layer
        Args:
            prompts: list of dicts with prompt data
            aoi_features (Optional): list of tuples with AOI features in pixel coordinates.
        """

        try:
            # Show loading indicator
            self.iface.messageBar().pushMessage("Getting prediction...", level=Qgis.Info)
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
            self.model_path = self.model_dropdown.currentText().strip()

            model_conditions = [
                (self.is_sam_model(), "sam"),
                (self.is_sam2_model(), "sam2"),
            ]

            self.model_type = "segment"
            for condition, model_type in model_conditions:
                if condition:
                    self.model_type = model_type

            if self.model_path:
                payload["model_path"] = self.model_path
                payload["model_type"] = self.model_type

            if aoi_features:
                payload["aoi"] = {
                    "type": "Rectangle",  # Must include the type field
                    "coordinates": []
                }
                if isinstance(aoi_features, tuple) and len(aoi_features) == 4:
                    # change tuple to list
                    payload["aoi"]["coordinates"] = list(aoi_features)
                elif isinstance(aoi_features, QgsGeometry):
                    # Convert QgsGeometry to a tuple with 4 coordinates
                    coords = aoi_features.boundingBox().toRectF()
                    payload["aoi"]["coordinates"] = [coords.xMinimum(), coords.yMinimum(), coords.xMaximum(), coords.yMaximum()]
                else:
                    QMessageBox.critical(None, "Error", "Invalid AOI feature format. Expected tuple with 4 coordinates or QgsGeometry.")
                    return

            # Show payload in message bar
            if prompts is None or len(prompts) == 0:
                formatted_payload = (
                    f"Sending to server:\n"
                    f"- Host image path: {container_image_path}\n"
                    f"- No prompts provided, running prediction without prompts.\n"
                    f"- Model path: {self.model_path}\n"
                    f"- Model type: {self.model_type}\n"
                    f"- AOI: {aoi_features}\n"
                )
            else:
                # print prompts to the logger
                self.logger.debug(f"Prompts: {json.dumps(prompts, indent=2)}")
                formatted_payload = (
                    f"Sending to server:\n"
                    f"- Host image path: {container_image_path}\n"
                    f"- Host embedding path: {embedding_path}\n"
                    f"- (re)Save embeddings: {save_embeddings}\n"
                    f"- Prompts: {json.dumps(prompts, indent=2)}\n"
                    f"- Model path: {self.model_path}\n"
                    f"- Model type: {self.model_type}\n"
                )

            self.iface.messageBar().pushMessage(
                "Server Request",
                formatted_payload,
                level=Qgis.Info,
                duration=5
            )

            # Send request to SAM server
            try:
                response = requests.post(f"{self.server_url}/predict", json=payload, timeout=6000000)

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

                        self.add_features_to_layer(features, "predictions", crs=feature_crs, model_path=self.model_path) # adds the predictions as a layer

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
            # QMessageBox.critical(None, "Error", f"Failed to get prediction: {str(e)}")
            tb = traceback.format_exc()
            self.iface.messageBar().pushMessage(f'{tb}', level=Qgis.Info)
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
                embeddings_dir = os.path.join(self.base_dir, 'embeddings') if os.path.exists(os.path.join(self.base_dir, 'embeddings')) else self.base_dir
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
        
        if host_path and host_path.startswith(self.images_dir) and self.docker_mode_button.isChecked():
            relative_path = os.path.relpath(host_path, self.images_dir)

            return os.path.join('/usr/src/app/easyearth_base/images', relative_path)
        
        return host_path

    def create_prediction_layers(self):
        """Prepare for prediction and prompt layers"""
        try:
            # Create temporary file paths
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.temp_prompts_geojson = os.path.join(self.tmp_dir, f'prompts_{timestamp}.geojson')
            self.temp_predictions_geojson = os.path.join(self.tmp_dir, f'predictions_{timestamp}.geojson')
            self.logger.info(f"Prepared file paths: \n"
                             f"Prompts: {self.temp_prompts_geojson}\n"
                             f"Predictions: {self.temp_predictions_geojson}")

            # Enable drawing controls
            # if self.is_sam_model():
            self.draw_button.setEnabled(True)

            # Enable prediction (no prompts) controls
            self.predict_button.setEnabled(True)

        except Exception as e:
            self.logger.error(f"Error preparing layers: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to prepare layers: {str(e)}")

    def on_layer_selected(self, index):
        """Handle layer selection change and check for existing embeddings"""
        try:
            if index > 0: # 0th index is "Select a layer..."
                layer_id = self.layer_dropdown.itemData(index)
                self.selected_layer = QgsProject.instance().mapLayer(layer_id) if layer_id else None

                if not self.selected_layer:
                    return

                self.image_path.setText(self.selected_layer.source())
                self.on_image_selected()
                self.create_prediction_layers()

                # Check for existing embedding
                layer_source = self.selected_layer.source()
                image_name = os.path.splitext(os.path.basename(layer_source))[0]
                self.update_embeddings(image_name)
        except Exception as e:
            self.logger.error(f"Error handling layer selection: {str(e)}")
            self.logger.exception("Full traceback:")
            QMessageBox.critical(None, "Error", f"Failed to handle layer selection: {str(e)}")

    # def cleanup_docker(self):
    #     """Prompt user to stop Docker when closing QGIS."""
    #     try:
    #         if self.docker_running:
    #             reply = QMessageBox.question(
    #                 None,
    #                 "Stop Docker Container",
    #                 "Do you want to stop the EasyEarth Docker container before exiting QGIS?",
    #                 QMessageBox.Yes | QMessageBox.No,
    #                 QMessageBox.No
    #             )
    #             if reply == QMessageBox.Yes:
    #                 self.stop_server()
    #     except Exception as e:
    #         self.logger.error(f"Error cleaning up Docker: {str(e)}")

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
            self.prediction_count = 0
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

            # self.cleanup_docker() # cleans up Docker resources

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

            if self.local_server_log_file:
                self.local_server_log_file.close()

            self.logger.debug("Plugin unloaded successfully")
        except Exception as e:
            self.logger.error(f"Error during plugin unload: {str(e)}")
            self.logger.exception("Full traceback:")
