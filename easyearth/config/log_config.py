import os

from datetime import datetime
import logging
import sys
from pathlib import Path

def setup_logger(name="easyearth", log_dir=None, level=logging.DEBUG):
    """
    Set up logging for the application.
    """
    # Determine log directory
    if log_dir is None:
        log_dir = Path(os.environ.get('BASE_DIR', '.')) / "logs"
    else:
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create unique log file
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    # Configure root logger (force=True for repeated calls, Python 3.8+)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='a'),
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )

    logger = logging.getLogger(name)
    logger.info(f"Logging to {log_file}")

    return logger
