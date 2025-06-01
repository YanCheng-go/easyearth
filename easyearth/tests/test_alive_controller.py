# coding: utf-8

import unittest
import requests

class TestAliveController(unittest.TestCase):
    def setUp(self):
        self.base_url = "http://localhost:3781/easyearth"

    def test_ping(self):
        response = requests.get(f"{self.base_url}/ping")
        self.assertEqual(response.status_code, 200)
        print(f"Ping response: {response.text}")

if __name__ == "__main__":
    unittest.main()

if __name__ == "__main__":
    unittest.main()
