# coding: utf-8

"""Tests to verify model_type and model_path are included in predict responses."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import unittest
from unittest.mock import MagicMock, patch

# Mock heavy dependencies before importing the controller
for mod_name in ['flask', 'flask_cors', 'flask_marshmallow', 'marshmallow_sqlalchemy',
    'connexion', 'rasterio', 'rasterio.errors', 'torch', 'PIL', 'PIL.Image',
    'easyearth.models.langsam', 'easyearth.models.sam', 'easyearth.models.easy_sam2',
    'easyearth.models.segmentation', 'easyearth.config.log_config']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

sys.modules['flask'].request = MagicMock()
sys.modules['flask'].jsonify = lambda x: x

import logging
sys.modules['easyearth.config.log_config'].setup_logger = lambda: logging.getLogger('easyearth')

import easyearth.controllers.predict_controller as predict_module


class TestModelInfoInResponse(unittest.TestCase):
    """Test that model_type and model_path appear in successful predict responses."""

    def _run_predict(self, model_type, model_path):
        """Helper: run predict with given model_type/model_path, return response body."""
        fake_geojson = {"type": "FeatureCollection", "features": []}

        # Mock request.get_json
        predict_module.request.get_json.return_value = {
            'model_type': model_type,
            'model_path': model_path,
            'image_path': '/tmp/test.tif',
            'prompts': [{'type': 'Point', 'data': {'points': [[100, 100]]}}],
        }

        # Mock verify_image_path
        with patch.object(predict_module, 'verify_image_path', return_value=True), \
             patch.object(predict_module, 'os') as mock_os, \
             patch.object(predict_module, 'rasterio') as mock_rio, \
             patch.object(predict_module, 'np') as mock_np, \
             patch.object(predict_module, 'reorganize_prompts') as mock_reorg, \
             patch.object(predict_module, 'Sam') as MockSam, \
             patch.object(predict_module, 'SamText') as MockSamText, \
             patch.object(predict_module, 'SAM2') as MockSAM2, \
             patch.object(predict_module, 'Segmentation') as MockSegmentation, \
             patch.object(predict_module, 'torch') as mock_torch, \
             patch.object(predict_module, 'json') as mock_json, \
             patch('builtins.open', MagicMock()):

            mock_os.environ = {'BASE_DIR': '/tmp'}
            mock_os.path.join = lambda *args: '/'.join(args)
            mock_os.path.basename = lambda p: p.split('/')[-1]
            mock_os.path.exists.return_value = False

            # Setup rasterio mock
            mock_dataset = MagicMock()
            mock_dataset.crs.to_string.return_value = 'EPSG:4326'
            mock_dataset.transform = MagicMock()
            mock_dataset.read.return_value = MagicMock()
            mock_rio.open.return_value.__enter__ = MagicMock(return_value=mock_dataset)
            mock_rio.open.return_value.__exit__ = MagicMock(return_value=False)

            # Setup numpy mock
            mock_image_array = MagicMock()
            mock_image_array.shape = (100, 100, 3)
            mock_np.transpose.return_value = mock_image_array
            mock_np.array.return_value = mock_image_array

            # Setup prompt reorganization
            mock_reorg.return_value = {
                'points': [[100, 100]],
                'labels': [1],
                'boxes': [],
                'text': ['tree'],
            }

            # Setup model mocks
            mock_sam_instance = MagicMock()
            mock_sam_instance.get_image_embeddings.return_value = MagicMock()
            mock_sam_instance.get_masks.return_value = (MagicMock(), MagicMock())
            mock_sam_instance.raster_to_vector.return_value = fake_geojson
            MockSam.return_value = mock_sam_instance

            mock_langsam_instance = MagicMock()
            mock_langsam_instance.get_masks.return_value = ([MagicMock()], MagicMock())
            mock_langsam_instance.raster_to_vector.return_value = fake_geojson
            MockSamText.return_value = mock_langsam_instance

            mock_sam2_instance = MagicMock()
            mock_sam2_instance.get_masks.return_value = MagicMock()
            mock_sam2_instance.raster_to_vector.return_value = fake_geojson
            MockSAM2.return_value = mock_sam2_instance

            mock_seg_instance = MagicMock()
            mock_seg_instance.segment.return_value = MagicMock()
            mock_seg_instance.raster_to_vector.return_value = fake_geojson
            MockSegmentation.return_value = mock_seg_instance

            result = predict_module.predict()
            return result

    def test_sam_model_info_in_response(self):
        """Test that model_type and model_path are in response for SAM model."""
        body, status_code = self._run_predict('sam', 'facebook/sam-vit-base')
        self.assertEqual(status_code, 200)
        self.assertEqual(body['model_type'], 'sam')
        self.assertEqual(body['model_path'], 'facebook/sam-vit-base')
        self.assertEqual(body['status'], 'success')

    def test_langsam_model_info_in_response(self):
        """Test that model_type and model_path are in response for LangSAM model."""
        body, status_code = self._run_predict('langsam', 'CIDAS/clipseg-rd64-refined')
        self.assertEqual(status_code, 200)
        self.assertEqual(body['model_type'], 'langsam')
        self.assertEqual(body['model_path'], 'CIDAS/clipseg-rd64-refined')

    def test_segment_model_info_in_response(self):
        """Test that model_type and model_path are in response for segmentation model."""
        body, status_code = self._run_predict('segment', 'nvidia/segformer-b0')
        self.assertEqual(status_code, 200)
        self.assertEqual(body['model_type'], 'segment')
        self.assertEqual(body['model_path'], 'nvidia/segformer-b0')

    def test_response_contains_all_expected_keys(self):
        """Test that response contains status, features, crs, model_type, and model_path."""
        body, status_code = self._run_predict('sam', 'facebook/sam-vit-base')
        for key in ['status', 'features', 'crs', 'model_type', 'model_path']:
            self.assertIn(key, body, f"Response missing expected key: {key}")


if __name__ == '__main__':
    unittest.main()
