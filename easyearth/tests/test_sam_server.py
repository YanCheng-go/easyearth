import unittest
import requests

class TestSAMServer(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.base_url = "http://localhost:3781/v1/easyearth"
        self.test_image_path = "https://huggingface.co/ybelkada/segment-anything/resolve/main/assets/car.png"  # Replace with actual test image path
        self.input_points = [[[850, 1100]], [[2250, 1000]]]
        self.input_boxes = [[[620, 900, 1000, 1255]], [[2000, 800, 2500, 1200]]]
        self.input_labels = [[1]]

    def test_health_check(self):
        """Test the health check endpoint"""
        response = requests.get(f"{self.base_url}/ping")
        self.assertEqual(response.status_code, 200)

    def test_predict_with_point_prompts(self):
        """Test prediction with point prompts"""
        payload = {
            "image_path": self.test_image_path,
            "model_type": "sam",
            "model_path": "facebook/sam-vit-base",
            "prompts": [
                {
                    "type": "Point",
                    "data": {"points": self.input_points[0], "labels": self.input_labels[0]}
                },
            ]
        }
        
        response = requests.post(
            f"{self.base_url}/predict",
            json=payload
        )
        
        self.assertEqual(response.status_code, 200)

    def test_predict_with_box_prompts(self):
        """Test prediction with box prompts"""
        payload = {
            "image_path": self.test_image_path,
            "model_type": "sam",
            "model_path": "facebook/sam-vit-base",
            "prompts": [
                {
                    "type": "Box",
                    "data": {"boxes": self.input_boxes[0]}
                },
            ]
        }
        
        response = requests.post(
            f"{self.base_url}/predict",
            json=payload
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('features', response.json())

    def test_predict_with_multiple_prompt_types(self):
        """Test prediction with multiple prompt types"""
        payload = {
            "image_path": self.test_image_path,
            "model_type": "sam",
            "model_path": "facebook/sam-vit-base",
            "prompts": [
                {
                    "type": "Point",
                    "data": {"points": self.input_points[0], "labels": self.input_labels[0]}
                },
                {
                    "type": "Box",
                    "data": {"boxes": self.input_boxes[0]}
                }
            ]
        }
        
        response = requests.post(
            f"{self.base_url}/predict",
            json=payload
        )
        
        self.assertEqual(response.status_code, 200)

    def test_invalid_image_path(self):
        """Test error handling for invalid image path"""
        payload = {
            "image_path": "nonexistent/image.tif",
            "model_type": "sam",
            "model_path": "facebook/sam-vit-base",
            "prompts": [
                {
                    "type": "Point",
                    "data": {"points": self.input_points[0], "labels": self.input_labels[0]}
                }
            ]
        }
        
        response = requests.post(
            f"{self.base_url}/predict",
            json=payload
        )
        
        self.assertEqual(response.status_code, 500)

if __name__ == '__main__':
    unittest.main()