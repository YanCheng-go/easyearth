from datetime import datetime
import logging
import os
import sys

def setup_logger(name="predict-controller"):
    """
    Set up logging for the application
    """
    # Get environment variables for directories
    APP_DIR = os.environ.get('APP_DIR', '/usr/src/app')
    LOG_DIR = os.environ.get('LOG_DIR', os.path.join(APP_DIR, 'logs'))
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f'{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

    # Configure root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'),  # 'a' for append mode
            logging.StreamHandler(sys.stdout)  # This will print to Docker logs
        ]
    )
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.info(f"Logging to {log_file}")
    return logger
