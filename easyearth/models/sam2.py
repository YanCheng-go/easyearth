"""
SAM2 model for Earth Observation tasks.
Reference: https://docs.ultralytics.com/models/sam-2/#how-to-use-sam-2-versatility-in-image-and-video-segmentation
"""

import os
import numpy as np
import requests
from PIL import Image
from ultralytics import SAM

try:
    from .base_model import BaseModel
except ImportError:
    from base_model import BaseModel

class SAM2(BaseModel):
    """SAM2 model for Earth Observation tasks."""

    map_model_path = {
        'ultralytics/sam2.1_b': 'sam2.1_b.pt',
        'ultralytics/sam2.1_l': 'sam2.1_l.pt',
        'ultralytics/sam2.1_x': 'sam2.1_x.pt'
    }

    def __init__(self, model_path: str = "ultralytics/sam2.1_b"):
        """Initialize SAM2 model."""
        super().__init__(model_path)
        model_path = model_path or "ultralytics/sam2.1_b"
        self.model_path = SAM2.map_model_path.get(model_path, None)
        if not self.model_path:
            raise ValueError(f"Model {model_path} not found. Available: {list(SAM2.map_model_path.keys())}")
        self.model_path = os.path.join(self.cache_dir, self.model_path)
        self.model = SAM(self.model_path)
        self.logger.info(f"Using SAM2 model from {model_path}")
        self.logger.debug(f"Cache directory: {self.cache_dir}")

    def get_masks(self, image_path: str, bboxes=None, points=None, labels=None):
        """
        Run inference on the given image with optional prompts.

        Args:
            image_path (str): Path to the input image.
            bboxes (list, optional): List of bounding boxes [x1, y1, x2, y2] or list of such boxes.
            points (list, optional): List of points or list of list of points.
            labels (list, optional): Labels for the points.

        Returns:
            list: List of masks (numpy arrays) for the segmented objects.
        """
        results = self.model(image_path, bboxes=bboxes, points=points, labels=labels)

        masks = []
        for result in results:
            mask = result.masks.data.cpu().numpy()
            # Convert to binary mask (1: mask, 0: background)
            mask = (mask > 0).astype(np.uint8)
            masks.append(mask)
        return masks


if __name__ == '__main__':
    # Example usage
    image_url = "https://huggingface.co/ybelkada/segment-anything/resolve/main/assets/car.png"
    raw_image = Image.open(requests.get(image_url, stream=True).raw).convert("RGB")
    raw_image.save("/tmp/example_image.png")

    sam2 = SAM2()
    masks = sam2.get_masks("/tmp/example_image.png", bboxes=[100, 100, 200, 200])
    geojson = sam2.raster_to_vector(masks, None, '/tmp/masks_sam2.geojson')
    print("Generated masks and saved geojson.")


    # Uncomment the following lines to run inference with different prompts
    # # Load a model
    # model = SAM(os.path.join(easyearth_SAM.cache_dir, "sam2.1_b.pt"))
    # # Display model information (optional)
    # model.info()
    # # Run inference with bboxes prompt
    # results = model(raw_image, bboxes=[100, 100, 200, 200])
    # # Run inference with single point
    # results = model(points=[900, 370], labels=[1])
    # # Run inference with multiple points
    # results = model(points=[[400, 370], [900, 370]], labels=[1, 1])
    # # Run inference with multiple points prompt per object
    # results = model(points=[[[400, 370], [900, 370]]], labels=[[1, 1]])
    # # Run inference with negative points prompt
    # results = model(points=[[[400, 370], [900, 370]]], labels=[[1, 0]])