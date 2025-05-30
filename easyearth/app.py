import logging

from easyearth import init_api
import os

app = init_api()  # Create the app as a module-level variable

def pre_check():
    # Check if the application is running with the correct user permissions
    if os.name == 'nt':
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            logger.warning("Running as an administrator. This is not recommended for security reasons.")
        else:
            logger.info("Running as a non-administrator user. This is the recommended practice.")
    else:
        if os.geteuid() == 0:
            logger.warning("Running as root user. This is not recommended for security reasons.")
        else:
            logger.info("Running as non-root user. This is the recommended practice.")

    # check the permissions of cache directory, # if it is not writable, log a warning
    cache_dir = os.environ.get('MODEL_CACHE_DIR', os.path.join(os.path.expanduser("~"), ".cache", "easyearth", "models"))
    if not os.access(cache_dir, os.W_OK):
        logger.warning(f"Cache directory {cache_dir} is not writable. Please check permissions.")
    else:
        logger.info(f"Cache directory {cache_dir} is writable.")

if __name__ == "__main__":
    # Set up logging
    logger = logging.getLogger("easyearth")
    logger.info("Starting EasyEarth API server")
    # Configuration pre-checks before starting the app
    pre_check()
    # Start the Flask app
    app.run(host="0.0.0.0", port=3781)