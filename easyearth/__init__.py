import connexion
from flask_cors import CORS
from flask_marshmallow import Marshmallow

from easyearth.config.log_config import setup_logger

ma = Marshmallow()
logger = setup_logger()

def init_api():
    app = connexion.App(__name__, specification_dir='./openapi/')
    app.add_api('swagger.yaml', 
                arguments={'title': 'EasyEarth API'},
                pythonic_params=True,
                base_path='')
    CORS(app.app)
    ma.init_app(app.app)
    return app