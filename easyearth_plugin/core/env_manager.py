import os
import subprocess
from qgis.core import Qgis
from qgis.PyQt.QtWidgets import QMessageBox
import logging

class EnvManager:
    """
    Python environment manager for EasyEarth plugin.
    """
    def __init__(self, iface, logs_dir, plugin_dir):
        """
        Initialize the environment manager.
        Args:
            iface: QGIS interface instance.
            logs_dir: Directory to store log files.
            plugin_dir: Directory where the plugin is located.
        """
        self.iface = iface
        self.logs_dir = logs_dir
        self.plugin_dir = plugin_dir

        self.download_env_log_file = None
        self.logger = logging.getLogger("easyearth_plugin")

    def download_linux_env(self):
        """ Download the Linux environment from Google Drive.
        This method runs a shell script to download the environment setup for Linux.
        It logs the output to a file and provides feedback to the user.
        """
        self.download_env_log_file = open(
            os.path.join(self.logs_dir, "download_linux_env.log"), "w"
        )

        download_script = os.path.join(self.plugin_dir, "download_linux_env.sh")
        if not os.path.exists(download_script):
            self.iface.messageBar().pushMessage(
                "Download script not found",
                level=Qgis.Critical
            )
            QMessageBox.critical(
                None,
                "Error",
                "Download script not found. Please use Docker mode for Linux."
            )
            return

        # Run the download script
        result = subprocess.Popen(
            f'bash \"{download_script}\"',
            shell=True,
            stdout=self.download_env_log_file,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True
        )

        self.iface.messageBar().pushMessage(
            "Downloading environment from Google Drive...",
            level=Qgis.Info
        )

        # Wait for the process to complete
        result.wait()
        if result.returncode != 0:
            self.logger.error("Failed to download the environment.")
            QMessageBox.critical(
                None,
                "Download Error",
                "Failed to download the environment. Check logs for details."
            )
            self.download_env_log_file.close()
            self.download_env_log_file = None
            return

        self.download_env_log_file.close()
        self.download_env_log_file = None
        self.logger.info("Download process completed. Check logs for details.")
        self.iface.messageBar().pushMessage("Download completed", level=Qgis.Success)
