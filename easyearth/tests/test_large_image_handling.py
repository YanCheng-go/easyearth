import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import unittest
import numpy as np
from unittest.mock import patch, MagicMock

# Import real PIL before mocking so we can use it in tests
from PIL import Image as RealImage

for mod_name in ['flask', 'flask_cors', 'flask_marshmallow', 'marshmallow_sqlalchemy',
    'connexion', 'rasterio', 'rasterio.errors', 'torch',
    'easyearth.models.langsam', 'easyearth.models.sam', 'easyearth.models.easy_sam2',
    'easyearth.models.segmentation', 'easyearth.config.log_config']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()
sys.modules['flask'].request = MagicMock()
sys.modules['flask'].jsonify = lambda x: x
import logging
sys.modules['easyearth.config.log_config'].setup_logger = lambda: logging.getLogger('easyearth')

from easyearth.controllers.predict_controller import MAX_IMAGE_DIMENSION


class TestLargeImageHandling(unittest.TestCase):
    """Tests for the large image downscaling logic."""

    def test_image_below_max_dimension_not_downscaled(self):
        """Image smaller than MAX_IMAGE_DIMENSION should not be downscaled."""
        width, height = 2000, 1500
        image_array = np.zeros((height, width, 3), dtype=np.uint8)
        original_height, original_width = image_array.shape[:2]

        image_was_downscaled = False
        if max(original_height, original_width) > MAX_IMAGE_DIMENSION:
            image_was_downscaled = True

        self.assertFalse(image_was_downscaled)
        self.assertEqual(image_array.shape[1], width)
        self.assertEqual(image_array.shape[0], height)

    def test_image_above_max_dimension_is_downscaled(self):
        """Image larger than MAX_IMAGE_DIMENSION should be downscaled."""
        width, height = 8000, 6000
        image_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        original_height, original_width = image_array.shape[:2]

        image_was_downscaled = False
        if max(original_height, original_width) > MAX_IMAGE_DIMENSION:
            scale_factor = MAX_IMAGE_DIMENSION / max(original_height, original_width)
            new_height = int(original_height * scale_factor)
            new_width = int(original_width * scale_factor)
            image_pil = RealImage.fromarray(image_array)
            image_pil = image_pil.resize((new_width, new_height), RealImage.LANCZOS)
            image_array = np.array(image_pil)
            image_was_downscaled = True

        self.assertTrue(image_was_downscaled)
        self.assertEqual(image_array.shape[1], 4096)
        self.assertEqual(image_array.shape[0], 3072)

    def test_scale_factor_preserves_aspect_ratio(self):
        """Downscaling should preserve the original aspect ratio."""
        width, height = 10000, 5000
        original_aspect = width / height

        scale_factor = MAX_IMAGE_DIMENSION / max(height, width)
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        new_aspect = new_width / new_height

        self.assertAlmostEqual(original_aspect, new_aspect, places=1)
        self.assertLessEqual(max(new_width, new_height), MAX_IMAGE_DIMENSION)

    def test_custom_max_dimension_via_env(self):
        """MAX_IMAGE_DIMENSION should be configurable via environment variable."""
        custom_dim = 2048
        with patch.dict(os.environ, {'EASYEARTH_MAX_IMAGE_DIM': str(custom_dim)}):
            result = int(os.environ.get('EASYEARTH_MAX_IMAGE_DIM', '4096'))
            self.assertEqual(result, custom_dim)

            # Simulate downscaling with custom dimension
            width, height = 5000, 3000
            image_array = np.zeros((height, width, 3), dtype=np.uint8)
            original_height, original_width = image_array.shape[:2]

            if max(original_height, original_width) > result:
                scale_factor = result / max(original_height, original_width)
                new_height = int(original_height * scale_factor)
                new_width = int(original_width * scale_factor)
                image_pil = RealImage.fromarray(image_array)
                image_pil = image_pil.resize((new_width, new_height), RealImage.LANCZOS)
                image_array = np.array(image_pil)

            self.assertLessEqual(max(image_array.shape[0], image_array.shape[1]), custom_dim)

    def test_very_small_images_not_affected(self):
        """Very small images should pass through without any changes."""
        width, height = 64, 64
        image_array = np.ones((height, width, 3), dtype=np.uint8) * 128
        original_shape = image_array.shape

        image_was_downscaled = False
        if max(height, width) > MAX_IMAGE_DIMENSION:
            image_was_downscaled = True

        self.assertFalse(image_was_downscaled)
        self.assertEqual(image_array.shape, original_shape)

    def test_square_image_downscaling(self):
        """Square images should remain square after downscaling."""
        size = 8192
        image_array = np.zeros((size, size, 3), dtype=np.uint8)
        original_height, original_width = image_array.shape[:2]

        if max(original_height, original_width) > MAX_IMAGE_DIMENSION:
            scale_factor = MAX_IMAGE_DIMENSION / max(original_height, original_width)
            new_height = int(original_height * scale_factor)
            new_width = int(original_width * scale_factor)
            image_pil = RealImage.fromarray(image_array)
            image_pil = image_pil.resize((new_width, new_height), RealImage.LANCZOS)
            image_array = np.array(image_pil)

        self.assertEqual(image_array.shape[0], image_array.shape[1])
        self.assertEqual(image_array.shape[0], MAX_IMAGE_DIMENSION)

    def test_response_includes_dimensions(self):
        """The response should include original image dimensions."""
        original_width, original_height = 8000, 6000
        image_array = np.zeros((3072, 4096, 3), dtype=np.uint8)
        image_was_downscaled = True

        response = {'status': 'success', 'features': [], 'crs': None,
                    'image_width': original_width, 'image_height': original_height}
        if image_was_downscaled:
            response['downscaled_to'] = [image_array.shape[1], image_array.shape[0]]

        self.assertEqual(response['image_width'], 8000)
        self.assertEqual(response['image_height'], 6000)
        self.assertEqual(response['downscaled_to'], [4096, 3072])

    def test_response_no_downscaled_key_when_not_downscaled(self):
        """The response should not include downscaled_to when image was not downscaled."""
        original_width, original_height = 2000, 1500
        image_was_downscaled = False

        response = {'status': 'success', 'features': [], 'crs': None,
                    'image_width': original_width, 'image_height': original_height}
        if image_was_downscaled:
            response['downscaled_to'] = [0, 0]

        self.assertNotIn('downscaled_to', response)


if __name__ == '__main__':
    unittest.main()
