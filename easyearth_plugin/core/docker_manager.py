"""Manage Docker containers for EasyEarth plugin. Handles all Docker-related logic: starting/stopping containers, checking status, managing images, and running commands with sudo."""
import subprocess
import json

from easyearth_plugin.core.utils import setup_logger

class DockerManager:
    """Manage Docker containers for EasyEarth plugin."""

    def __init__(self, iface, logger=None):
        """Initialize DockerManager with QGIS interface and optional logger."""
        if logger is None:
            self.logger = setup_logger(name="DockerManager")
            self.logger.info("DockerManager initialized")
        self.iface = iface

    def inspect_running_container(self, docker_path):
        """Inspect the running Docker container to get the mounted data directory"""
        try:
            result = subprocess.run(f"{docker_path} inspect easyearth", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                self.logger.error(f"Failed to inspect Docker container: {result.stderr}")
                return '', False

            docker_running = False
            base_dir = ''

            # check if docker container is running
            if not result.stdout:
                docker_running = False
            else:
                docker_running = True

                # Parse the JSON output
                container_info = json.loads(result.stdout)
                mounts = container_info[0].get('Mounts', [])
                for mount in mounts:
                    if mount['Destination'] == '/usr/src/app/easyearth_base':
                        base_dir = mount['Source']  # Get the host directory mounted to /usr/src/app/data
                    if mount['Destination'] == '/usr/src/app/.cache/models':
                        cache_dir = mount['Source']
            return base_dir, docker_running
        except:
            self.logger.error(f"Failed to inspect Docker container: {result.stderr if 'result' in locals() else 'Unknown error'}")
            return '', False
