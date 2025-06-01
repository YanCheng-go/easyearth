import logging

from flask_testing import TestCase

from easyearth import init_api


class BaseTestCase(TestCase):
    @staticmethod
    def create_app():
        logging.getLogger("connexion.operation").setLevel("ERROR")
        app = init_api()
        return app.app

    @staticmethod
    def base_url(url):
        return f"/v1/basic/{url}"
