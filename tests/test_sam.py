"""Test functions in easyearth.sam module."""

from PIL import Image
import requests
import torch

from easyearth.models.sam import Sam

import logging

logger = logging.getLogger("easyearth")

class TestSam:
    """Test the Sam class"""

    def __init__(self):
        """Initialize the test class"""

        self.sam = Sam(model_path="facebook/sam-vit-huge")
        self.embedding_dim = [1, 256, 64, 64]

        self.image_url = "https://huggingface.co/ybelkada/segment-anything/resolve/main/assets/car.png"
        self.raw_image = Image.open(requests.get(self.image_url, stream=True).raw).convert("RGB")

        # TODO: debug input dimensions
        self.input_points = [[[850, 1100]]]
        self.input_boxes = [[[620, 900, 1000, 1255]]]
        self.input_labels = [[1]]

    def test_get_image_embeddings(self):
        """Test the get_image_embeddings function"""
        image_embeddings = self.sam.get_image_embeddings(self.raw_image)
        assert image_embeddings is not None
        assert image_embeddings.shape == torch.Size(self.embedding_dim)

    def test_points(self):
        """Test the get_masks function with points"""
        image_embeddings = self.sam.get_image_embeddings(self.raw_image)
        masks, scores = self.sam.get_masks(self.raw_image, input_points=self.input_points, image_embeddings=image_embeddings)
        assert len(masks[0]) == 1
        assert len(scores) == 1

    def test_boxes(self):
        """Test the get_masks function with bounding boxes"""
        image_embeddings = self.sam.get_image_embeddings(self.raw_image)
        masks, scores = self.sam.get_masks(self.raw_image, input_boxes=self.input_boxes, image_embeddings=image_embeddings)
        assert len(masks[0]) == 1
        assert len(scores) == 1

    def test_multiple(self):
        """Test the get_masks function with multiple prompts"""
        image_embeddings = self.sam.get_image_embeddings(self.raw_image)
        masks, scores = self.sam.get_masks(self.raw_image, input_points=self.input_points, input_boxes=self.input_boxes, image_embeddings=image_embeddings)
        assert len(masks[0]) == 1
        assert len(scores) == 1

    def test_labels(self):
        # TODO: add test for labels
        """Test the get_masks function with labels"""
        image_embeddings = self.sam.get_image_embeddings(self.raw_image)
        masks, scores = self.sam.get_masks(self.raw_image, input_labels=self.input_labels, image_embeddings=image_embeddings)
        assert len(masks[0]) == 1
        assert len(scores) == 1


# Execution function
def test_main():
    """Run the tests"""
    test = TestSam()
    test.test_get_image_embeddings()
    # test.test_get_masks()
    test.test_points()
    test.test_boxes()
    test.test_multiple()
    test.test_labels()


if __name__ == "__main__":
    test_main()

