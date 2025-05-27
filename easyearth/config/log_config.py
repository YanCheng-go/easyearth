import logging
import os
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "easyearth_logger"

def create_log():
    plugin_dir = os.environ.get('EASYEARTH_PLUGIN_DIR')

    if not os.path.exists(f"{plugin_dir}/logs"):
        os.makedirs(f"{plugin_dir}/logs")

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    handler_local = RotatingFileHandler(f"{plugin_dir}/logs/{LOGGER_NAME}.log", mode="a", maxBytes=50000, backupCount=10)
    logger.addHandler(handler_local)
    
    return logger
