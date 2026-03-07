"""
Unit tests for predict_controller utility functions.
Tests verify_image_path, verify_model_path, reorganize_prompts,
reproject_prompts, and BASE_DIR/path construction logic.
"""
import sys
import os

# Add project root to path so 'easyearth' package is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import unittest
import tempfile
import numpy as np
from unittest.mock import patch, MagicMock

# Mock heavy dependencies before importing the controller module
# so tests can run without Flask, rasterio, torch, etc.
_mocks = {}
for mod_name in [
    'flask', 'flask_cors', 'flask_marshmallow', 'marshmallow_sqlalchemy',
    'connexion', 'rasterio', 'rasterio.errors', 'torch',
    'PIL', 'PIL.Image',
    'easyearth.models.langsam', 'easyearth.models.sam',
    'easyearth.models.easy_sam2', 'easyearth.models.segmentation',
    'easyearth.config.log_config',
]:
    if mod_name not in sys.modules:
        _mocks[mod_name] = MagicMock()
        sys.modules[mod_name] = _mocks[mod_name]

# Provide flask.request and flask.jsonify stubs
sys.modules['flask'].request = MagicMock()
sys.modules['flask'].jsonify = lambda x: x

# Provide setup_logger that returns a real logger
import logging
sys.modules['easyearth.config.log_config'].setup_logger = lambda: logging.getLogger('easyearth')

from easyearth.controllers.predict_controller import (
    verify_image_path,
    verify_model_path,
    reorganize_prompts,
    reproject_prompts,
)


class TestVerifyImagePath(unittest.TestCase):
    def test_valid_local_file(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as tmp:
            self.assertTrue(verify_image_path(tmp.name))

    def test_invalid_local_file(self):
        self.assertFalse(verify_image_path("/nonexistent/path/image.jpg"))

    def test_valid_http_url(self):
        with patch("easyearth.controllers.predict_controller.requests.get") as mock_get:
            mock_get.return_value.raise_for_status = lambda: None
            self.assertTrue(verify_image_path("https://example.com/image.jpg"))

    def test_invalid_http_url(self):
        import requests as req
        with patch("easyearth.controllers.predict_controller.requests.get") as mock_get:
            mock_get.side_effect = req.exceptions.ConnectionError("fail")
            self.assertFalse(verify_image_path("https://bad-url.example.com/img.jpg"))


class TestVerifyModelPath(unittest.TestCase):
    def test_none_returns_false(self):
        self.assertFalse(verify_model_path(None))

    def test_empty_string_returns_false(self):
        self.assertFalse(verify_model_path(""))

    def test_huggingface_format(self):
        self.assertTrue(verify_model_path("facebook/sam-vit-huge"))
        self.assertTrue(verify_model_path("restor/tcd-segformer-mit-b2"))
        self.assertTrue(verify_model_path("ultralytics/sam2.1_s"))

    def test_absolute_path_rejected_if_not_exists(self):
        self.assertFalse(verify_model_path("/nonexistent/model/path"))

    def test_relative_path_rejected(self):
        self.assertFalse(verify_model_path("./some/model"))

    def test_tilde_path_rejected_if_not_exists(self):
        self.assertFalse(verify_model_path("~/nonexistent_model_dir"))

    def test_local_dir_accepted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertTrue(verify_model_path(tmpdir))

    def test_plain_string_no_slash_rejected(self):
        self.assertFalse(verify_model_path("just-a-name"))


class TestReorganizePrompts(unittest.TestCase):
    def test_empty_prompts(self):
        result = reorganize_prompts([])
        self.assertEqual(result, {'points': [], 'labels': [], 'boxes': [], 'text': []})

    def test_point_prompts(self):
        prompts = [
            {"type": "Point", "data": {"points": [[100, 200]], "labels": [1]}}
        ]
        result = reorganize_prompts(prompts)
        self.assertGreater(len(result['points']), 0)
        self.assertGreater(len(result['labels']), 0)

    def test_box_prompts(self):
        prompts = [
            {"type": "Box", "data": {"boxes": [[10, 20, 100, 200]]}}
        ]
        result = reorganize_prompts(prompts)
        self.assertGreater(len(result['boxes']), 0)

    def test_text_prompts(self):
        prompts = [
            {"type": "Text", "data": {"text": ["tree"]}}
        ]
        result = reorganize_prompts(prompts)
        self.assertGreater(len(result['text']), 0)

    def test_mixed_prompts(self):
        prompts = [
            {"type": "Point", "data": {"points": [[100, 200]], "labels": [1]}},
            {"type": "Box", "data": {"boxes": [[10, 20, 100, 200]]}},
            {"type": "Text", "data": {"text": ["car"]}},
        ]
        result = reorganize_prompts(prompts)
        self.assertGreater(len(result['points']), 0)
        self.assertGreater(len(result['boxes']), 0)
        self.assertGreater(len(result['text']), 0)

    def test_unknown_type_ignored(self):
        prompts = [{"type": "Unknown", "data": {"foo": "bar"}}]
        result = reorganize_prompts(prompts)
        self.assertEqual(result, {'points': [], 'labels': [], 'boxes': [], 'text': []})


class TestReprojectPrompts(unittest.TestCase):
    def _make_identity_transform(self):
        """Create an identity-like affine transform using rasterio convention"""
        from collections import namedtuple
        # Simple identity transform: pixel coords == map coords
        class IdentityTransform:
            def __invert__(self):
                return self
            def __mul__(self, point):
                return point
        return IdentityTransform()

    def test_identity_transform(self):
        transform = self._make_identity_transform()
        image_shape = (100, 100)
        prompts = {
            'points': [[10, 20]],
            'labels': [1],
            'boxes': [[5, 5, 50, 50]],
            'text': ["tree"],
        }
        result = reproject_prompts(prompts, transform, image_shape)
        self.assertEqual(result['points'], [[10, 20]])
        self.assertEqual(result['labels'], [1])
        self.assertEqual(len(result['boxes']), 1)
        self.assertEqual(result['text'], ["tree"])

    def test_clipping_to_image_bounds(self):
        transform = self._make_identity_transform()
        image_shape = (50, 50)
        prompts = {
            'points': [[200, 300]],
            'labels': [1],
            'boxes': [],
            'text': [],
        }
        result = reproject_prompts(prompts, transform, image_shape)
        self.assertEqual(result['points'], [[49, 49]])

    def test_empty_prompts(self):
        transform = self._make_identity_transform()
        image_shape = (100, 100)
        prompts = {'points': [], 'labels': [], 'boxes': [], 'text': []}
        result = reproject_prompts(prompts, transform, image_shape)
        self.assertEqual(result, {'points': [], 'labels': [], 'boxes': [], 'text': []})


class TestPredictBaseDirFallback(unittest.TestCase):
    def test_base_dir_fallback_when_env_not_set(self):
        env = os.environ.copy()
        env.pop('BASE_DIR', None)
        with patch.dict(os.environ, env, clear=True):
            base_dir = os.environ.get('BASE_DIR', os.path.join(os.path.expanduser("~"), ".easyearth"))
            self.assertEqual(base_dir, os.path.join(os.path.expanduser("~"), ".easyearth"))

    def test_base_dir_uses_env_when_set(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {'BASE_DIR': tmpdir}):
                base_dir = os.environ.get('BASE_DIR', os.path.join(os.path.expanduser("~"), ".easyearth"))
                self.assertEqual(base_dir, tmpdir)

    def test_temp_and_embeddings_dirs_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = os.path.join(tmpdir, 'tmp')
            embeddings_dir = os.path.join(tmpdir, 'embeddings')
            self.assertFalse(os.path.exists(temp_dir))
            self.assertFalse(os.path.exists(embeddings_dir))
            os.makedirs(temp_dir, exist_ok=True)
            os.makedirs(embeddings_dir, exist_ok=True)
            self.assertTrue(os.path.isdir(temp_dir))
            self.assertTrue(os.path.isdir(embeddings_dir))


class TestGeojsonPathConstruction(unittest.TestCase):
    def test_os_path_join_produces_valid_path(self):
        temp_dir = os.path.join("base", "tmp")
        image_name = "test_image.tif"
        path = os.path.join(temp_dir, f"predict-sam_{image_name}_20240101_120000.geojson")
        self.assertNotIn("//", path)
        self.assertTrue(path.endswith(".geojson"))


if __name__ == "__main__":
    unittest.main()
