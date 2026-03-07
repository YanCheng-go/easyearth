import sys
import os
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Mock heavy dependencies before importing
for mod_name in ['flask', 'flask_cors', 'flask_marshmallow', 'marshmallow_sqlalchemy',
    'connexion', 'rasterio', 'rasterio.errors', 'torch', 'PIL', 'PIL.Image',
    'easyearth.models.langsam', 'easyearth.models.sam', 'easyearth.models.easy_sam2',
    'easyearth.models.segmentation', 'easyearth.config.log_config']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

import numpy as np


def select_bands(image_array, bands=None):
    """
    Standalone band selection logic matching the predict controller implementation.

    Args:
        image_array: numpy array with shape (H, W) or (H, W, C)
        bands: list of 1-indexed band indices, or None for default behavior

    Returns:
        numpy array with shape (H, W, 3) ready for model input
    """
    if bands is not None:
        if len(image_array.shape) == 2:
            raise ValueError("Cannot select bands from a single-band image")
        num_bands = image_array.shape[2]
        for b in bands:
            if b < 1 or b > num_bands:
                raise ValueError(
                    f"Band index {b} is out of range. Image has {num_bands} band(s) "
                    f"(valid range: 1 to {num_bands})"
                )
        image_array = image_array[:, :, [b - 1 for b in bands]]
        # If fewer than 3 bands selected, stack to 3 channels
        if image_array.shape[2] == 1:
            image_array = np.stack([image_array[:, :, 0]] * 3, axis=-1)
        elif image_array.shape[2] == 2:
            padding = np.zeros(image_array.shape[:2], dtype=image_array.dtype)
            image_array = np.stack(
                [image_array[:, :, 0], image_array[:, :, 1], padding], axis=-1
            )
    else:
        # Default behavior
        if len(image_array.shape) == 2:
            image_array = np.stack([image_array] * 3, axis=-1)
        elif image_array.shape[2] > 3:
            image_array = image_array[:, :, :3]
    return image_array


class TestMultiBandInput(unittest.TestCase):
    """Tests for multi-band input handling in the predict controller."""

    def setUp(self):
        """Create test images with known band values."""
        self.height = 10
        self.width = 10
        # 5-band image where each band is filled with its 1-indexed band number
        self.five_band = np.zeros((self.height, self.width, 5), dtype=np.uint8)
        for i in range(5):
            self.five_band[:, :, i] = i + 1  # band values: 1,2,3,4,5

        # 3-band image
        self.three_band = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        for i in range(3):
            self.three_band[:, :, i] = (i + 1) * 10

        # 2-band image
        self.two_band = np.zeros((self.height, self.width, 2), dtype=np.uint8)
        self.two_band[:, :, 0] = 100
        self.two_band[:, :, 1] = 200

        # Single-band (2D) image
        self.single_band = np.full((self.height, self.width), 42, dtype=np.uint8)

    def test_default_no_bands_more_than_3(self):
        """Default behavior: >3 bands takes first 3."""
        result = select_bands(self.five_band, bands=None)
        self.assertEqual(result.shape, (self.height, self.width, 3))
        # Should be first 3 bands (values 1, 2, 3)
        np.testing.assert_array_equal(result[:, :, 0], 1)
        np.testing.assert_array_equal(result[:, :, 1], 2)
        np.testing.assert_array_equal(result[:, :, 2], 3)

    def test_specify_bands_123(self):
        """Specifying bands=[1,2,3] should select first 3 bands."""
        result = select_bands(self.five_band, bands=[1, 2, 3])
        self.assertEqual(result.shape, (self.height, self.width, 3))
        np.testing.assert_array_equal(result[:, :, 0], 1)
        np.testing.assert_array_equal(result[:, :, 1], 2)
        np.testing.assert_array_equal(result[:, :, 2], 3)

    def test_specify_bands_reorder(self):
        """Specifying bands=[4,3,2] should reorder bands."""
        result = select_bands(self.five_band, bands=[4, 3, 2])
        self.assertEqual(result.shape, (self.height, self.width, 3))
        np.testing.assert_array_equal(result[:, :, 0], 4)
        np.testing.assert_array_equal(result[:, :, 1], 3)
        np.testing.assert_array_equal(result[:, :, 2], 2)

    def test_invalid_band_index_too_high(self):
        """Invalid band index (too high) should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            select_bands(self.five_band, bands=[1, 2, 6])
        self.assertIn("out of range", str(ctx.exception))
        self.assertIn("6", str(ctx.exception))

    def test_invalid_band_index_zero(self):
        """Band index 0 (below 1-indexed minimum) should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            select_bands(self.five_band, bands=[0, 1, 2])
        self.assertIn("out of range", str(ctx.exception))

    def test_invalid_band_index_negative(self):
        """Negative band index should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            select_bands(self.three_band, bands=[-1, 1, 2])
        self.assertIn("out of range", str(ctx.exception))

    def test_single_band_stacked_to_3_channels(self):
        """Selecting a single band should stack it to 3 channels."""
        result = select_bands(self.five_band, bands=[4])
        self.assertEqual(result.shape, (self.height, self.width, 3))
        # All 3 channels should have band 4's value
        np.testing.assert_array_equal(result[:, :, 0], 4)
        np.testing.assert_array_equal(result[:, :, 1], 4)
        np.testing.assert_array_equal(result[:, :, 2], 4)

    def test_two_band_image_no_bands_param(self):
        """2-band image without bands param should pass through unchanged (<=3 bands)."""
        result = select_bands(self.two_band, bands=None)
        self.assertEqual(result.shape, (self.height, self.width, 2))
        np.testing.assert_array_equal(result[:, :, 0], 100)
        np.testing.assert_array_equal(result[:, :, 1], 200)

    def test_single_band_2d_default(self):
        """2D single-band image with default behavior should stack to 3 channels."""
        result = select_bands(self.single_band, bands=None)
        self.assertEqual(result.shape, (self.height, self.width, 3))
        np.testing.assert_array_equal(result[:, :, 0], 42)
        np.testing.assert_array_equal(result[:, :, 1], 42)
        np.testing.assert_array_equal(result[:, :, 2], 42)

    def test_single_band_2d_with_bands_raises(self):
        """2D single-band image with bands param should raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            select_bands(self.single_band, bands=[1])
        self.assertIn("Cannot select bands from a single-band image", str(ctx.exception))

    def test_three_band_no_change(self):
        """3-band image without bands param stays unchanged."""
        result = select_bands(self.three_band, bands=None)
        self.assertEqual(result.shape, (self.height, self.width, 3))
        np.testing.assert_array_equal(result[:, :, 0], 10)
        np.testing.assert_array_equal(result[:, :, 1], 20)
        np.testing.assert_array_equal(result[:, :, 2], 30)

    def test_two_bands_selected_padded(self):
        """Selecting 2 bands should pad with zeros for the third channel."""
        result = select_bands(self.five_band, bands=[1, 5])
        self.assertEqual(result.shape, (self.height, self.width, 3))
        np.testing.assert_array_equal(result[:, :, 0], 1)
        np.testing.assert_array_equal(result[:, :, 1], 5)
        np.testing.assert_array_equal(result[:, :, 2], 0)


if __name__ == '__main__':
    unittest.main()
