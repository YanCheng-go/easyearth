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
        else:
            self.logger = logger
            self.logger.info("DockerManager initialized")
        self.iface = iface

    def is_container_running(self, docker_path, container_name):
        # Run 'docker ps' to list running containers
        result = subprocess.run(
            [docker_path, "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True, text=True
        )
        # Check if the container name appears in the output
        return container_name in result.stdout.strip().splitlines()

    def inspect_running_container(self, docker_path, base_dir):
        """Inspect the running Docker container to get the mounted data directory"""
        try:
            self.logger.info("Inspecting running Docker container for EasyEarth using docker ps")
            # Use subprocess to run the docker inspect command
            is_container_running = self.is_container_running(docker_path, "easyearth")

            if not is_container_running:
                self.logger.info("Docker container 'easyearth' is not running")
                return base_dir, False

            self.logger.info("Docker container is running")
            result = subprocess.run(f"{docker_path} inspect easyearth", capture_output=True, text=True, shell=True)
            if result.returncode != 0:
                self.logger.error(f"Failed to inspect Docker container: {result.stderr}")
                return '', False

            docker_running = False

            # check if docker container is running
            if result.stdout.strip():
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
            return base_dir, False
