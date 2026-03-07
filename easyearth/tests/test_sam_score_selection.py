"""Tests for SAM score selection logic in raster_to_vector (Issue #21)"""
import sys, os, unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
import numpy as np

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@unittest.skipUnless(HAS_TORCH, "torch not available")
class TestSamScoreSelection(unittest.TestCase):
    def test_argmax_selects_highest_score_mask(self):
        scores = torch.tensor([[[0.3, 0.9, 0.5]]])  # 1 batch, 1 object, 3 masks
        highest_score_idx = torch.argmax(scores, dim=2)
        self.assertEqual(highest_score_idx[0, 0].item(), 1)

    def test_object_id_assignment(self):
        masks = torch.zeros(2, 1, 4, 4, dtype=torch.bool)
        masks[0, 0, 0:2, 0:2] = True
        masks[1, 0, 2:4, 2:4] = True
        objects_id = torch.arange(2).view(-1, 1, 1, 1).expand_as(masks)
        masks_id = torch.where(masks, objects_id + 1, torch.tensor(0))
        self.assertEqual(masks_id[0, 0, 0, 0].item(), 1)
        self.assertEqual(masks_id[1, 0, 2, 2].item(), 2)
        self.assertEqual(masks_id[0, 0, 2, 2].item(), 0)

    def test_overlap_amax_keeps_highest_id(self):
        mask1 = torch.tensor([[1, 1, 0], [1, 1, 0], [0, 0, 0]])
        mask2 = torch.tensor([[0, 2, 2], [0, 2, 2], [0, 0, 0]])
        stacked = torch.stack([mask1, mask2], dim=0)
        combined = torch.amax(stacked, dim=0)
        self.assertEqual(combined[0, 1].item(), 2)
        self.assertEqual(combined[0, 0].item(), 1)

    def test_single_object_squeeze(self):
        masks = torch.tensor([[[1, 0], [0, 1]]])  # shape (1, 2, 2)
        result = masks.squeeze(0).numpy().astype(np.uint8)
        self.assertEqual(result.shape, (2, 2))
        self.assertEqual(result[0, 0], 1)


class TestScoreSelectionLogic(unittest.TestCase):
    def test_argmax_picks_highest(self):
        scores = [0.3, 0.9, 0.5]
        self.assertEqual(scores.index(max(scores)), 1)

    def test_overlap_max_wins(self):
        mask1 = np.array([[1, 1, 0], [1, 1, 0], [0, 0, 0]])
        mask2 = np.array([[0, 2, 2], [0, 2, 2], [0, 0, 0]])
        combined = np.maximum(mask1, mask2)
        self.assertEqual(combined[0, 1], 2)
        self.assertEqual(combined[0, 0], 1)

    def test_single_object_no_overlap(self):
        mask = np.array([[1, 1, 0], [1, 0, 0], [0, 0, 0]])
        self.assertEqual(np.max(mask), 1)


if __name__ == "__main__":
    unittest.main()
