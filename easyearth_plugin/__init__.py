def classFactory(iface):
    # setup logger
    from easyearth_plugin.core.utils import setup_logger
    logger = setup_logger(name="easyearth_plugin")
    logger.info("Initializing EasyEarth Plugin")

    from .plugin import EasyEarthPlugin
    return EasyEarthPlugin(iface)