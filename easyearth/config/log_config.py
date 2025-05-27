import logging
import os
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "easyearth_logger"

def create_log():
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    handler_local = RotatingFileHandler(f"logs/{LOGGER_NAME}.log", mode="a", maxBytes=50000, backupCount=10)
    logger.addHandler(handler_local)
    
    return logger
