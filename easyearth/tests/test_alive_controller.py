# coding: utf-8

from __future__ import absolute_import

from easyearth.tests import BaseTestCase


class BaseTestAliveController(BaseTestCase):
    def test_get_alive(self):
        response = self.client.open("/v1/easyearth/ping", method="GET")
        print(f"Response: {response.data}")  # Add debug output
        self.assert200(response)


if __name__ == "__main__":
    # TODO: unittest cannot find urls, but the testing works when running the app first and enter the url on the web browser
    import unittest

    unittest.main()
