"""General utility functions: logging setup, file operations, path conversions, and other helpers."""

import os
import logging
from datetime import datetime

def setup_logger(name="EasyEarth"):
    """Set up and return a logger for the plugin (singleton pattern)."""
    logger = logging.getLogger(name)
    if getattr(logger, "_is_configured", False):
        return logger  # Prevent adding handlers multiple times

    plugin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    log_dir = os.path.join(plugin_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"plugin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.DEBUG)

    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("=== EasyEarth Plugin Started ===")
    logger.info(f"Log file: {log_file}")

    logger._is_configured = True  # Mark as configured
    logger.log_file = log_file    # Optional: attach log file path

    return logger