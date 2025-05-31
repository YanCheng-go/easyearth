"""General utility functions: logging setup, file operations, path conversions, and other helpers."""

import logging
from pathlib import Path
from datetime import datetime

def setup_logger(name="easyearth_plugin", log_dir=None, level=logging.DEBUG):
    """
    Set up and return a logger for the plugin (singleton pattern).

    Args:
        name (str): Name of the logger.
        log_dir (str or Path, optional): Custom directory for log files.
        level (int): Logging level.

    Returns:
        logging.Logger: Configured logger object.
    """
    logger = logging.getLogger(name)
    if getattr(logger, "_is_configured", False):
        return logger  # Prevent re-adding handlers

    # Determine log directory
    if log_dir is None:
        # Default: logs/ under the parent of this file
        plugin_dir = Path(__file__).resolve().parent.parent
        log_dir = plugin_dir / "logs"
    else:
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # File handler
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # Reset and add handlers
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Mark as configured and attach log file path
    logger._is_configured = True
    logger.log_file = str(log_file)

    logger.info("=== EasyEarth Plugin Started ===")
    logger.info(f"Log file: {log_file}")

    return logger