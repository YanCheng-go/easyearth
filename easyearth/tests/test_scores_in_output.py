"""Tests for score inclusion in GeoJSON prediction output (Issue #74)"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from unittest.mock import MagicMock

for mod_name in ['flask', 'flask_cors', 'flask_marshmallow', 'marshmallow_sqlalchemy',
    'connexion', 'rasterio', 'rasterio.errors', 'torch', 'PIL', 'PIL.Image',
    'shapely', 'shapely.geometry', 'geopandas', 'rasterio.features',
    'easyearth.models.langsam', 'easyearth.models.sam', 'easyearth.models.easy_sam2',
    'easyearth.models.segmentation', 'easyearth.config.log_config',
    'torch.backends', 'torch.backends.mps']:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()

sys.modules['flask'].request = MagicMock()
sys.modules['flask'].jsonify = lambda x: x

import logging
sys.modules['easyearth.config.log_config'].setup_logger = lambda: logging.getLogger('easyearth')

# Make torch.backends.mps.is_available() return False
sys.modules['torch'].backends.mps.is_available.return_value = False
sys.modules['torch'].cuda.is_available.return_value = False


def add_scores_to_geojson(geojson, best_scores):
    """Replicates the score-addition logic from Sam.raster_to_vector"""
    for feature in geojson:
        uid = feature['properties'].get('uid')
        if uid in best_scores:
            feature['properties']['score'] = round(best_scores[uid], 4)
    return geojson


class TestScoresInOutput(unittest.TestCase):
    """Test that confidence scores are correctly added to GeoJSON features"""

    def test_single_object_score(self):
        """Score should be added to a single feature with matching uid"""
        geojson = [
            {'properties': {'uid': 1}, 'geometry': {'type': 'Polygon', 'coordinates': []}}
        ]
        best_scores = {1: 0.987654}
        result = add_scores_to_geojson(geojson, best_scores)

        self.assertEqual(len(result), 1)
        self.assertIn('score', result[0]['properties'])
        self.assertEqual(result[0]['properties']['score'], 0.9877)

    def test_multiple_objects_scores(self):
        """Scores should be added to multiple features with matching uids"""
        geojson = [
            {'properties': {'uid': 1}, 'geometry': {'type': 'Polygon', 'coordinates': []}},
            {'properties': {'uid': 2}, 'geometry': {'type': 'Polygon', 'coordinates': []}},
            {'properties': {'uid': 3}, 'geometry': {'type': 'Polygon', 'coordinates': []}},
        ]
        best_scores = {1: 0.95, 2: 0.88, 3: 0.72}
        result = add_scores_to_geojson(geojson, best_scores)

        self.assertEqual(result[0]['properties']['score'], 0.95)
        self.assertEqual(result[1]['properties']['score'], 0.88)
        self.assertEqual(result[2]['properties']['score'], 0.72)

    def test_no_scores(self):
        """Features should remain unchanged when no scores are provided"""
        geojson = [
            {'properties': {'uid': 1}, 'geometry': {'type': 'Polygon', 'coordinates': []}}
        ]
        best_scores = {}
        result = add_scores_to_geojson(geojson, best_scores)

        self.assertNotIn('score', result[0]['properties'])

    def test_empty_geojson(self):
        """Empty geojson list should be handled gracefully"""
        geojson = []
        best_scores = {1: 0.95}
        result = add_scores_to_geojson(geojson, best_scores)

        self.assertEqual(len(result), 0)

    def test_uid_not_in_scores(self):
        """Features with uids not in best_scores should not get a score"""
        geojson = [
            {'properties': {'uid': 5}, 'geometry': {'type': 'Polygon', 'coordinates': []}}
        ]
        best_scores = {1: 0.95}
        result = add_scores_to_geojson(geojson, best_scores)

        self.assertNotIn('score', result[0]['properties'])

    def test_score_rounding(self):
        """Scores should be rounded to 4 decimal places"""
        geojson = [
            {'properties': {'uid': 1}, 'geometry': {'type': 'Polygon', 'coordinates': []}}
        ]
        best_scores = {1: 0.123456789}
        result = add_scores_to_geojson(geojson, best_scores)

        self.assertEqual(result[0]['properties']['score'], 0.1235)

    def test_existing_properties_preserved(self):
        """Existing properties should not be removed when adding score"""
        geojson = [
            {'properties': {'uid': 1, 'label': 'tree'}, 'geometry': {'type': 'Polygon', 'coordinates': []}}
        ]
        best_scores = {1: 0.95}
        result = add_scores_to_geojson(geojson, best_scores)

        self.assertEqual(result[0]['properties']['uid'], 1)
        self.assertEqual(result[0]['properties']['label'], 'tree')
        self.assertEqual(result[0]['properties']['score'], 0.95)


if __name__ == '__main__':
    unittest.main()
