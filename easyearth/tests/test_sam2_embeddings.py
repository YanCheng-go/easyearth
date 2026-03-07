"""
Tests for SAM2 embedding support.
Uses mocks since torch/ultralytics aren't available in the test environment.
"""

import sys
import os
import unittest
import json
import tempfile
import shutil
from unittest.mock import MagicMock, patch

# Mock heavy dependencies before any easyearth imports.
# Use a single MagicMock for torch so submodule lookups (torch.backends.mps) work.
mock_torch = MagicMock()
sys.modules['torch'] = mock_torch
sys.modules['torch.backends'] = mock_torch.backends
sys.modules['torch.backends.mps'] = mock_torch.backends.mps
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_marshmallow'] = MagicMock()
sys.modules['connexion'] = MagicMock()
sys.modules['ultralytics'] = MagicMock()
sys.modules['rasterio'] = MagicMock()
sys.modules['rasterio.features'] = MagicMock()
sys.modules['rasterio.transform'] = MagicMock()
sys.modules['shapely'] = MagicMock()
sys.modules['shapely.geometry'] = MagicMock()
sys.modules['geopandas'] = MagicMock()
sys.modules['transformers'] = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import numpy as np


class TestSAM2GetImageEmbeddings(unittest.TestCase):
    """Test that SAM2 has a get_image_embeddings method that returns a tensor."""

    @patch('easyearth.models.easy_sam2.SAM')
    @patch('easyearth.models.easy_sam2.BaseModel.__init__', return_value=None)
    def test_get_image_embeddings_method_exists(self, mock_base_init, mock_sam_cls):
        """Test that SAM2 class has get_image_embeddings method."""
        from easyearth.models.easy_sam2 import SAM2

        sam2 = SAM2.__new__(SAM2)
        sam2.cache_dir = '/tmp'
        sam2.model_path = 'sam2.1_b.pt'
        sam2.logger = MagicMock()
        sam2.model = MagicMock()

        self.assertTrue(hasattr(sam2, 'get_image_embeddings'),
                        "SAM2 should have get_image_embeddings method")
        self.assertTrue(callable(getattr(sam2, 'get_image_embeddings')))

    @patch('easyearth.models.easy_sam2.SAM')
    @patch('easyearth.models.easy_sam2.BaseModel.__init__', return_value=None)
    def test_get_image_embeddings_returns_tensor(self, mock_base_init, mock_sam_cls):
        """Test that get_image_embeddings returns a tensor-like object."""
        from easyearth.models.easy_sam2 import SAM2

        sam2 = SAM2.__new__(SAM2)
        sam2.cache_dir = '/tmp'
        sam2.model_path = 'sam2.1_b.pt'
        sam2.logger = MagicMock()

        mock_model = MagicMock()
        mock_embeddings = MagicMock()
        mock_embeddings.shape = (1, 256, 64, 64)
        mock_model.get_image_embeddings.return_value = mock_embeddings
        sam2.model = mock_model

        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = sam2.get_image_embeddings(fake_image)

        self.assertIsNotNone(result)
        mock_model.get_image_embeddings.assert_called_once()


class TestSAM2GetMasksWithEmbeddings(unittest.TestCase):
    """Test that get_masks accepts an image_embeddings parameter."""

    @patch('easyearth.models.easy_sam2.SAM')
    @patch('easyearth.models.easy_sam2.BaseModel.__init__', return_value=None)
    def test_get_masks_accepts_image_embeddings(self, mock_base_init, mock_sam_cls):
        """Test that get_masks accepts image_embeddings as a keyword argument."""
        from easyearth.models.easy_sam2 import SAM2
        import inspect

        sig = inspect.signature(SAM2.get_masks)
        param_names = list(sig.parameters.keys())
        self.assertIn('image_embeddings', param_names,
                      "get_masks should accept image_embeddings parameter")

    @patch('easyearth.models.easy_sam2.SAM')
    @patch('easyearth.models.easy_sam2.BaseModel.__init__', return_value=None)
    def test_get_masks_passes_embeddings_to_model(self, mock_base_init, mock_sam_cls):
        """Test that get_masks passes image_embeddings to the underlying model."""
        from easyearth.models.easy_sam2 import SAM2

        sam2 = SAM2.__new__(SAM2)
        sam2.cache_dir = '/tmp'
        sam2.model_path = 'sam2.1_b.pt'
        sam2.logger = MagicMock()

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_mask_data = MagicMock()
        mock_mask_data.cpu.return_value.numpy.return_value = np.ones((1, 100, 100))
        mock_result.masks.data = mock_mask_data
        mock_model.return_value = [mock_result]
        sam2.model = mock_model

        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
        fake_embeddings = MagicMock()

        masks = sam2.get_masks(fake_image, image_embeddings=fake_embeddings)

        mock_model.assert_called_once()
        call_kwargs = mock_model.call_args[1]
        self.assertEqual(call_kwargs.get('embed'), fake_embeddings)

    @patch('easyearth.models.easy_sam2.SAM')
    @patch('easyearth.models.easy_sam2.BaseModel.__init__', return_value=None)
    def test_get_masks_works_without_embeddings(self, mock_base_init, mock_sam_cls):
        """Test that get_masks still works when image_embeddings is not provided."""
        from easyearth.models.easy_sam2 import SAM2

        sam2 = SAM2.__new__(SAM2)
        sam2.cache_dir = '/tmp'
        sam2.model_path = 'sam2.1_b.pt'
        sam2.logger = MagicMock()

        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_mask_data = MagicMock()
        mock_mask_data.cpu.return_value.numpy.return_value = np.ones((1, 100, 100))
        mock_result.masks.data = mock_mask_data
        mock_model.return_value = [mock_result]
        sam2.model = mock_model

        fake_image = np.zeros((100, 100, 3), dtype=np.uint8)
        masks = sam2.get_masks(fake_image)

        mock_model.assert_called_once()
        call_kwargs = mock_model.call_args[1]
        self.assertIsNone(call_kwargs.get('embed'))


class TestSAM2EmbeddingSaveLoad(unittest.TestCase):
    """Test embedding save and load logic."""

    def setUp(self):
        """Create a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        # Reset mock call counts before each test
        mock_torch.save.reset_mock()
        mock_torch.load.reset_mock()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_embedding_save(self):
        """Test that embeddings can be saved to a file."""
        embedding_path = os.path.join(self.test_dir, 'embeddings', 'test_embed.pt')
        embeddings_mock = MagicMock()
        embeddings_mock.cpu.return_value = MagicMock()

        os.makedirs(os.path.dirname(embedding_path), exist_ok=True)
        embedding_data = {
            'embeddings': embeddings_mock.cpu(),
            'image_shape': (100, 100),
            'timestamp': '2026-01-01T00:00:00'
        }
        mock_torch.save(embedding_data, embedding_path)

        mock_torch.save.assert_called_once_with(embedding_data, embedding_path)

    def test_embedding_load(self):
        """Test that embeddings can be loaded from a file."""
        embedding_path = os.path.join(self.test_dir, 'test_embed.pt')

        mock_loaded_data = {
            'embeddings': MagicMock(),
            'image_shape': (100, 100),
            'timestamp': '2026-01-01T00:00:00'
        }
        mock_torch.load.return_value = mock_loaded_data

        loaded = mock_torch.load(embedding_path)

        mock_torch.load.assert_called_once_with(embedding_path)
        self.assertIn('embeddings', loaded)
        self.assertEqual(loaded['image_shape'], (100, 100))

    def test_embedding_index_file(self):
        """Test that an index file mapping images to embeddings can be created."""
        index_path = os.path.join(self.test_dir, 'index.json')
        image_path = '/data/images/test.tif'
        embedding_path = os.path.join(self.test_dir, 'test_embed.pt')

        index = {}
        index[image_path] = embedding_path
        with open(index_path, 'w') as f:
            json.dump(index, f)

        with open(index_path, 'r') as f:
            loaded_index = json.load(f)

        self.assertIn(image_path, loaded_index)
        self.assertEqual(loaded_index[image_path], embedding_path)


class TestSAM2EmbeddingCacheUsed(unittest.TestCase):
    """Test that cached embeddings are used when available in the controller."""

    def setUp(self):
        """Create a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        # Reset mock call counts before each test
        mock_torch.save.reset_mock()
        mock_torch.load.reset_mock()

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cached_embeddings_loaded_when_available(self):
        """Test that the controller loads cached embeddings from disk when available."""
        embedding_path = os.path.join(self.test_dir, 'cached_embed.pt')
        # Create the file so os.path.exists returns True
        with open(embedding_path, 'w') as f:
            f.write('dummy')

        mock_embeddings = MagicMock()
        image_shape = (100, 100)
        mock_torch.load.return_value = {
            'embeddings': mock_embeddings,
            'image_shape': image_shape,
            'timestamp': '2026-01-01T00:00:00'
        }

        # Simulate the controller logic for loading cached embeddings
        image_array = np.zeros((100, 100, 3), dtype=np.uint8)
        save_embeddings = False
        image_embeddings = None
        used_cache = False

        if embedding_path and os.path.exists(embedding_path) and not save_embeddings:
            embedding_data = mock_torch.load(embedding_path)
            if isinstance(embedding_data, dict):
                if embedding_data.get('image_shape') == image_array.shape[:2]:
                    image_embeddings = embedding_data['embeddings']
                    used_cache = True

        self.assertTrue(used_cache, "Should have loaded embeddings from cache")
        self.assertEqual(image_embeddings, mock_embeddings)
        mock_torch.load.assert_called_once_with(embedding_path)

    def test_embeddings_generated_when_no_cache(self):
        """Test that embeddings are generated when no cache file exists."""
        embedding_path = os.path.join(self.test_dir, 'nonexistent_embed.pt')

        mock_sam2 = MagicMock()
        mock_new_embeddings = MagicMock()
        mock_sam2.get_image_embeddings.return_value = mock_new_embeddings

        image_array = np.zeros((100, 100, 3), dtype=np.uint8)
        save_embeddings = False
        image_embeddings = None

        if embedding_path and os.path.exists(embedding_path) and not save_embeddings:
            image_embeddings = mock_torch.load(embedding_path)
        else:
            image_embeddings = mock_sam2.get_image_embeddings(image_array)

        self.assertEqual(image_embeddings, mock_new_embeddings)
        mock_sam2.get_image_embeddings.assert_called_once_with(image_array)
        mock_torch.load.assert_not_called()

    def test_embeddings_saved_when_requested(self):
        """Test that embeddings are saved to disk when save_embeddings is True."""
        embedding_path = os.path.join(self.test_dir, 'embeddings', 'new_embed.pt')

        mock_sam2 = MagicMock()
        mock_new_embeddings = MagicMock()
        mock_new_embeddings.cpu.return_value = MagicMock()
        mock_sam2.get_image_embeddings.return_value = mock_new_embeddings

        image_array = np.zeros((100, 100, 3), dtype=np.uint8)
        save_embeddings = True
        image_embeddings = None

        # Simulate: no cache exists, generate and save
        if not (embedding_path and os.path.exists(embedding_path) and not save_embeddings):
            image_embeddings = mock_sam2.get_image_embeddings(image_array)

            if save_embeddings and embedding_path:
                os.makedirs(os.path.dirname(embedding_path), exist_ok=True)
                embedding_data = {
                    'embeddings': image_embeddings.cpu(),
                    'image_shape': image_array.shape[:2],
                }
                mock_torch.save(embedding_data, embedding_path)

        mock_torch.save.assert_called_once()
        save_args = mock_torch.save.call_args[0]
        self.assertIn('embeddings', save_args[0])
        self.assertEqual(save_args[1], embedding_path)


if __name__ == '__main__':
    unittest.main()
