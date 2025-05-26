import logging
import os
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "easyearth_example"


def create_log():
    if not os.path.exists("./logs"):
        os.makedirs("./logs")

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)

    handler_local = RotatingFileHandler(
        f"./logs/{LOGGER_NAME}.log", mode="a", maxBytes=50000, backupCount=10
    )
    logger.addHandler(handler_local)
    return logger
