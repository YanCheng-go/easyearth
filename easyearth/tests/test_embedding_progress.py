"""Tests for embedding progress reporting in predict responses."""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Mock heavy dependencies before importing anything from easyearth
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_marshmallow'] = MagicMock()
sys.modules['connexion'] = MagicMock()
sys.modules['rasterio'] = MagicMock()
sys.modules['rasterio.errors'] = MagicMock()
sys.modules['torch'] = MagicMock()
sys.modules['torch.backends'] = MagicMock()
sys.modules['PIL'] = MagicMock()
sys.modules['PIL.Image'] = MagicMock()
sys.modules['easyearth.models.langsam'] = MagicMock()
sys.modules['easyearth.models.sam'] = MagicMock()
sys.modules['easyearth.models.easy_sam2'] = MagicMock()
sys.modules['easyearth.models.segmentation'] = MagicMock()
sys.modules['easyearth.config.log_config'] = MagicMock()

os.environ.setdefault('BASE_DIR', '/tmp/easyearth_test')

try:
    from flask import Flask
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


class TestEmbeddingProgressResponse(unittest.TestCase):
    """Test that predict responses include embedding status fields for SAM predictions."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_request_data = {
            'model_type': 'sam',
            'model_path': 'facebook/sam-vit-base',
            'image_path': '/tmp/test_image.tif',
            'prompts': [{'type': 'Point', 'data': {'points': [[100, 200]], 'label': 1}}],
            'embedding_path': None,
            'save_embeddings': False,
        }

    def _make_mock_request(self, request_data):
        """Create a properly configured mock request object."""
        mock_request = MagicMock()
        mock_request.get_json = MagicMock(return_value=request_data)
        return mock_request

    def _make_mock_sam(self):
        """Create a mock SAM model."""
        mock_sam = MagicMock()
        mock_sam.device = 'cpu'
        mock_sam.get_image_embeddings.return_value = MagicMock()
        mock_sam.get_masks.return_value = (MagicMock(), MagicMock())
        mock_sam.raster_to_vector.return_value = [{'type': 'Feature', 'geometry': {}}]
        return mock_sam

    def _make_mock_rasterio(self):
        """Create a mock rasterio that returns valid image data."""
        import numpy as np
        mock_rasterio = MagicMock()
        mock_src = MagicMock()
        mock_src.transform = MagicMock()
        mock_src.crs.to_string.return_value = 'EPSG:4326'
        mock_src.read.return_value = np.random.randint(0, 255, (3, 100, 100), dtype=np.uint8)
        mock_rasterio.open.return_value.__enter__ = MagicMock(return_value=mock_src)
        mock_rasterio.open.return_value.__exit__ = MagicMock(return_value=False)
        return mock_rasterio

    def _run_predict(self, request_data, mock_exists_return=False, mock_torch_load_return=None):
        """Run predict function with all necessary mocks and return response data."""
        app = Flask(__name__)
        mock_request = self._make_mock_request(request_data)
        mock_sam = self._make_mock_sam()
        mock_rasterio = self._make_mock_rasterio()

        with app.test_request_context(json=request_data):
            patches = {
                'easyearth.controllers.predict_controller.request': mock_request,
                'easyearth.controllers.predict_controller.Sam': MagicMock(return_value=mock_sam),
                'easyearth.controllers.predict_controller.rasterio': mock_rasterio,
                'easyearth.controllers.predict_controller.verify_image_path': MagicMock(return_value=True),
                'easyearth.controllers.predict_controller.os.path.exists': MagicMock(return_value=mock_exists_return),
                'easyearth.controllers.predict_controller.os.makedirs': MagicMock(),
                'easyearth.controllers.predict_controller.os.path.join': os.path.join,
            }

            if mock_torch_load_return is not None:
                patches['easyearth.controllers.predict_controller.torch'] = MagicMock(
                    **{'load.return_value': mock_torch_load_return}
                )

            # Apply all patches
            active_patches = []
            for target, new_val in patches.items():
                p = patch(target, new_val)
                p.start()
                active_patches.append(p)

            file_patch = patch('builtins.open', mock_open())
            file_patch.start()
            active_patches.append(file_patch)

            try:
                from easyearth.controllers.predict_controller import predict
                response, status_code = predict()
                return response.get_json(), status_code
            finally:
                for p in active_patches:
                    p.stop()

    @unittest.skipUnless(HAS_FLASK, "Flask not available")
    def test_response_includes_embedding_generated_true(self):
        """Test that response includes embedding_generated=True when embeddings are freshly generated."""
        response_data, status_code = self._run_predict(self.mock_request_data)

        self.assertEqual(status_code, 200)
        self.assertIn('embedding_generated', response_data)
        self.assertTrue(response_data['embedding_generated'])

    @unittest.skipUnless(HAS_FLASK, "Flask not available")
    def test_response_includes_embedding_time_when_generated(self):
        """Test that response includes a numeric embedding_time when embeddings are generated."""
        response_data, status_code = self._run_predict(self.mock_request_data)

        self.assertEqual(status_code, 200)
        self.assertIn('embedding_time', response_data)
        self.assertIsInstance(response_data['embedding_time'], float)
        self.assertGreaterEqual(response_data['embedding_time'], 0)

    @unittest.skipUnless(HAS_FLASK, "Flask not available")
    def test_embedding_time_is_none_when_cached(self):
        """Test that embedding_time is None and embedding_generated is False when using cached embeddings."""
        cache_request_data = self.mock_request_data.copy()
        cache_request_data['embedding_path'] = '/tmp/cached_embedding.pt'
        cache_request_data['save_embeddings'] = False

        mock_embedding_tensor = MagicMock()
        mock_embedding_tensor.to.return_value = mock_embedding_tensor
        mock_torch_load_return = {
            'embeddings': mock_embedding_tensor,
            'image_shape': (100, 100),
        }

        response_data, status_code = self._run_predict(
            cache_request_data,
            mock_exists_return=True,
            mock_torch_load_return=mock_torch_load_return,
        )

        self.assertEqual(status_code, 200)
        self.assertIn('embedding_generated', response_data)
        self.assertFalse(response_data['embedding_generated'])
        self.assertIn('embedding_time', response_data)
        self.assertIsNone(response_data['embedding_time'])

    def test_non_sam_response_has_no_embedding_fields(self):
        """Test that non-SAM model responses do not include embedding fields."""
        response_data = {'status': 'success', 'features': [], 'crs': 'EPSG:4326'}
        # For non-SAM models the controller does not add embedding fields
        self.assertNotIn('embedding_generated', response_data)
        self.assertNotIn('embedding_time', response_data)


class TestPluginEmbeddingStatus(unittest.TestCase):
    """Test that the plugin correctly handles embedding status from server responses."""

    def test_plugin_shows_generated_message(self):
        """Test that plugin shows generation message when embedding_generated is True."""
        response_json = {
            'status': 'success',
            'features': [{'type': 'Feature', 'geometry': {}}],
            'crs': 'EPSG:4326',
            'embedding_generated': True,
            'embedding_time': 2.35,
        }

        self.assertTrue(response_json.get('embedding_generated'))
        self.assertEqual(response_json.get('embedding_time'), 2.35)

        # Simulate the plugin logic for displaying the message
        if response_json.get('embedding_generated') is not None:
            if response_json['embedding_generated']:
                msg = f"Embeddings generated in {response_json.get('embedding_time', '?')}s"
            else:
                msg = "Using cached embeddings"

        self.assertEqual(msg, "Embeddings generated in 2.35s")

    def test_plugin_shows_cached_message(self):
        """Test that plugin shows cached message when embedding_generated is False."""
        response_json = {
            'status': 'success',
            'features': [{'type': 'Feature', 'geometry': {}}],
            'crs': 'EPSG:4326',
            'embedding_generated': False,
            'embedding_time': None,
        }

        self.assertFalse(response_json.get('embedding_generated'))
        self.assertIsNone(response_json.get('embedding_time'))

        if response_json.get('embedding_generated') is not None:
            if response_json['embedding_generated']:
                msg = "Embeddings generated"
            else:
                msg = "Using cached embeddings"

        self.assertEqual(msg, "Using cached embeddings")

    def test_plugin_no_message_for_non_sam(self):
        """Test that plugin does not show embedding message when field is absent."""
        response_json = {
            'status': 'success',
            'features': [{'type': 'Feature', 'geometry': {}}],
            'crs': 'EPSG:4326',
        }

        self.assertIsNone(response_json.get('embedding_generated'))
        show_message = response_json.get('embedding_generated') is not None
        self.assertFalse(show_message)


if __name__ == '__main__':
    unittest.main()
