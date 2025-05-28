"""Manage Docker containers for EasyEarth plugin. Handles all Docker-related logic: starting/stopping containers, checking status, managing images, and running commands with sudo."""
from easyearth_plugin.core.utils import setup_logger

class DockerManager:
    """Manage Docker containers for EasyEarth plugin."""

    def __init__(self, logger):
        self.logger = setup_logger(name="DockerManager")
        self.logger.info("DockerManager initialized")

    def inspect_running_container(self, iface, docker_path, data_folder_edit, docker_run_btn):
        """Inspect the running Docker container to get the mounted data directory"""
        result = subprocess.run(f"{self.docker_path} inspect easyearth", capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            self.logger.error(f"Failed to inspect Docker container: {result.stderr}")
            return None

        # check if docker container is running
        if not result.stdout:
            self.docker_running = False
            self.docker_run_btn.setText("Run Docker")
            self.iface.messageBar().pushMessage("Info", "Docker container is not running", level=Qgis.Info, duration=5)
            return None
        else:
            self.docker_running = True
            self.docker_run_btn.setText("Stop Docker")
            self.iface.messageBar().pushMessage("Info", "Docker container is running", level=Qgis.Info, duration=5)

        # Parse the JSON output
        container_info = json.loads(result.stdout)
        mounts = container_info[0].get('Mounts', [])
        for mount in mounts:
            if mount['Destination'] == '/usr/src/app/data':
                self.data_dir = mount['Source']  # Get the host directory mounted to /usr/src/app/data
                # update the data folder edit line
                self.data_folder_edit.setText(self.data_dir)
                self.iface.messageBar().pushMessage("Info", f"Data folder set to: {self.data_dir}", level=Qgis.Info, duration=5)
            if mount['Destination'] == '/usr/src/app/tmp':
                self.tmp_dir = mount['Source']
                self.iface.messageBar().pushMessage("Info", f"Temporary directory set to: {self.tmp_dir}", level=Qgis.Info, duration=5)
            if mount['Destination'] == '/usr/src/app/logs':
                self.logs_dir = mount['Source']
                self.iface.messageBar().pushMessage("Info", f"Logs directory set to: {self.logs_dir}", level=Qgis.Info, duration=5)
            if mount['Destination'] == '/usr/src/app/.cache/models':
                self.cache_dir = mount['Source']
                self.iface.messageBar().pushMessage("Info", f"Cache directory set to: {self.cache_dir}", level=Qgis.Info, duration=5)
