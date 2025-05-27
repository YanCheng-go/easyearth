def classFactory(iface):
    from .plugin import EasyEarthPlugin
    return EasyEarthPlugin(iface)