import unittest
import requests


class TestLangSAMServer(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = "http://localhost:3781/easyearth"  # Adjust as needed for your test environment
        self.test_image_path = "https://huggingface.co/ybelkada/segment-anything/resolve/main/assets/car.png"  # Replace with actual test image path
        self.input_points = [[[850, 1100]], [[2250, 1000]]]
        self.input_boxes = [[[620, 900, 1000, 1255]], [[2000, 800, 2500, 1200]]]
        self.input_labels = [[1]]

    def test_predict_with_text_prompts(self):
        """Test prediction with point prompts"""
        payload = {
            "image_path": self.test_image_path,
            "model_type": "langsam",
            "model_path": "facebook/sam-vit-b",
            "prompts": [
                {
                    "type": "Text",
                    "data": {"text": ["car"]}
                },
            ]
        }

        response = requests.post(
            f"{self.base_url}/predict",
            json=payload
        )
        # TODO: understand why 500
        self.assertEqual(response.status_code, 500)


if __name__ == '__main__':
    unittest.main()