"""Test functions in easyearth.sam module."""

from PIL import Image
import requests
import torch

from easyearth.models.sam import Sam

class TestSam:
    """Test the Sam class"""

    def __init__(self):
        """Initialize the test class"""

        self.sam = Sam(model_version="facebook/sam-vit-huge")
        self.embedding_dim = [1, 256, 64, 64]

        self.image_url = "https://huggingface.co/ybelkada/segment-anything/resolve/main/assets/car.png"
        self.raw_image = Image.open(requests.get(self.image_url, stream=True).raw).convert("RGB")

        self.input_points = [[[850, 1100]], [[2250, 1000]]]
        self.input_boxes = [[[620, 900, 1000, 1255]], [[2000, 800, 2500, 1200]]]
        self.input_labels = ["car", "building"]

    def test_get_image_embeddings(self):
        """Test the get_image_embeddings function"""
        image_embeddings = self.sam.get_image_embeddings(self.sam.model, self.sam.processor, self.raw_image)
        assert image_embeddings is not None
        assert image_embeddings.shape == torch.Size(self.embedding_dim)

    def test_points(self):
        """Test the get_masks function with points"""
        image_embeddings = self.sam.get_image_embeddings(self.sam.model, self.sam.processor, self.raw_image)
        masks, scores = self.sam.get_masks(self.sam.model, self.raw_image, self.sam.processor, image_embeddings, input_points=self.input_points)
        assert len(masks[0]) == 2
        assert len(scores) == 2

    def test_boxes(self):
        """Test the get_masks function with bounding boxes"""
        image_embeddings = self.sam.get_image_embeddings(self.sam.model, self.sam.processor, self.raw_image)
        masks, scores = self.sam.get_masks(self.sam.model, self.raw_image, self.sam.processor, image_embeddings, input_boxes=self.input_boxes)
        assert len(masks[0]) == 2
        assert len(scores) == 2

    def test_multiple(self):
        """Test the get_masks function with multiple prompts"""
        image_embeddings = self.sam.get_image_embeddings(self.sam.model, self.sam.processor, self.raw_image)
        masks, scores = self.sam.get_masks(self.sam.model, self.raw_image, self.sam.processor, image_embeddings, input_points=self.input_points, input_boxes=self.input_boxes)
        assert len(masks[0]) == 4
        assert len(scores) == 4

    def test_labels(self):
        # TODO: add test for labels
        """Test the get_masks function with labels"""
        image_embeddings = self.sam.get_image_embeddings(self.sam.model, self.sam.processor, self.raw_image)
        masks, scores = self.sam.get_masks(self.sam.model, self.raw_image, self.sam.processor,image_embeddings, input_labels=self.input_labels)
        assert len(masks[0]) == 2
        assert len(scores) == 2


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

