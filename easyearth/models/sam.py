"""SAM model implementation
reference: https://colab.research.google.com/github/huggingface/notebooks/blob/main/examples/segment_anything.ipynb#scrollTo=UQ8meq5mDYQ1
"""

try:
    from .base_model import BaseModel
except ImportError:
    # For direct script execution
    from base_model import BaseModel
from pathlib import Path
from PIL import Image
from transformers import SamModel, SamProcessor
from typing import Optional, List, Tuple, Union, Any
import numpy as np
import torch
import requests
import rasterio

class Sam(BaseModel):
    def __init__(self, model_path: str = "facebook/sam-vit-huge"):
        """Initialize the SAM model
        Args:
            model_path: The model to use
        """
        super().__init__(model_path)
        self.model = SamModel.from_pretrained(model_path, cache_dir=self.cache_dir).to(self.device)
        self.processor = SamProcessor.from_pretrained(model_path, cache_dir=self.cache_dir)

    def get_metadata(self, image):
        """Get the metadata for a given image
        Args:
            image: The image to process
        Returns: The metadata
        """

        with rasterio.open(image) as src:
            metadata = src.meta
        return metadata

    def get_image_embeddings(self, raw_image: Union[Image.Image, np.ndarray]) -> torch.Tensor:
        """Get the image embeddings for a given image
        Args:
            raw_image: The image to process, np.ndarray
        Returns:
            The image embeddings
        """
        inputs = self.processor(raw_image, return_tensors="pt").to(self.device)
        image_embeddings = self.model.get_image_embeddings(inputs["pixel_values"])
        return image_embeddings

    def get_masks(self,
                 image: Union[str, Path, Image.Image, np.ndarray],
                 input_points: Optional[List] = None,
                 input_boxes: Optional[List] = None,
                 input_labels: Optional[List] = None,
                 image_embeddings: Optional[torch.Tensor] = None, 
                 multimask_output = True) -> Tuple[torch.Tensor, torch.Tensor]:
        """Get the masks for a given prompt
        Args:
            image: The image to process
            input_points: Optional point prompts
            input_boxes: Optional box prompts
            input_labels: Optional labels
            image_embeddings: Optional pre-computed embeddings
            multimask_output: Optional, if set to True, allowing one mask for one prompt point, but need to add one dimension to the point prompt.
        Returns:
            Tuple of (masks, scores)
        """
        if isinstance(image, str) or isinstance(image, Path):
            raw_image = Image.open(image).convert("RGB")
        else:
            raw_image = image

        if image_embeddings is None:
            image_embeddings = self.get_image_embeddings(raw_image)

        inputs = self.processor(
            raw_image,
            input_points=input_points,
            input_boxes=input_boxes,
            input_labels=input_labels,
            return_tensors="pt"
        )

        if torch.backends.mps.is_available():
            inputs = inputs.to(torch.float32).to(self.device)
        else:
            inputs = inputs.to(self.device)

        inputs.pop("pixel_values", None)
        inputs.update({"image_embeddings": image_embeddings})

        with torch.no_grad():
            outputs = self.model(**inputs, multimask_output=multimask_output) # TODO: so maybe at the moment do not allow hollow masks where it requires multimask_output=True...


        # TODO: should this be on gpu or cpu?
        masks = self.processor.image_processor.post_process_masks(
            outputs.pred_masks.cpu(),
            inputs["original_sizes"].cpu(),
            inputs["reshaped_input_sizes"].cpu()
        )
        scores = outputs.iou_scores.cpu()

        return masks, scores

    def raster_to_vector(self, masks: Union[torch.Tensor, np.ndarray], scores: Union[torch.Tensor, np.ndarray], img_transform: Optional[Any] = None, filename: Optional[str] = None):
        """Extends base raster_to_vector with SAM-specific processing
        Args:
            masks: The masks to process, [(Object, Mask, Height, Width)] -> One object may have multiple masks with different scores
            scores: The scores for the masks
            img_transform: The image transform
            filename: The filename to save the output
        Returns:
            geojson: The GeoJSON output of predicted masks
        """

        num_masks = masks[0].shape[0]
        num_scores = masks[0].shape[1]

        # get the object id for each mask
        objects_id = torch.arange(num_masks).view(-1, 1, 1, 1).expand_as(masks[0])  # the first dimension is the object id
        masks_id = torch.where(masks[0], objects_id + 1, torch.tensor(0))  # the second dimension is the mask id, one object may have multiple predicted masks with different confidence scores

        # if multimask_output is True, then we have multiple masks for each object with different scores, then we choose the one with the highest score
        if num_scores > 1:
            # TODO: verity if this is correct
            # Get the index of the mask with the highest iou score
            highes_score_idx = torch.argmax(scores, dim=2)
            assert highes_score_idx.shape[-1] == masks[0].shape[0]

            # Get the mask with the highest score
            masks_list = []
            for obj, sco in enumerate(highes_score_idx[0].tolist()):
                masks_list.append(masks_id[obj, sco, :, :])
                
            masks_highest = torch.stack(masks_list, dim=0)

            # Convert to the dimensions suitable for super().raster_to_vector
            masks_combined = masks_highest
        else:
            # Convert to the dimensions suitable for super().raster_to_vector
            masks_combined = masks_id.squeeze(1)

        # TODO: is there a better way? this will cause potential problems for overlapping predictions -> for now, the latter prediction will overwrite the former...
        # reduce the dimensions of the masks to 2D by choosing the largest value
        if masks_combined.shape[0] > 1:
            masks_combined = torch.amax(masks_combined, dim=0, keepdim=False).numpy().astype(np.uint8)

        return super().raster_to_vector([masks_combined], img_transform, filename)


if __name__ == "__main__":
    image_url = "https://huggingface.co/ybelkada/segment-anything/resolve/main/assets/car.png"
    raw_image = Image.open(requests.get(image_url, stream=True).raw).convert("RGB")
    img_transform = rasterio.transform.from_bounds(0, 0, 1024, 1024, 1024, 1024)

    input_points = [[[850, 1100], [2250, 1000]]]
    input_boxes = [[[650, 900, 1000, 1250]]]
    multiple_boxes = [[[620, 900, 1000, 1255], [2050, 800, 2400, 1150]]]
    input_labels = [[0]]
    multiple_points = [[[[850, 1100]], [[2250, 1000]]]]  # one mask for each point

    sam = Sam()
    image_embeddings = sam.get_image_embeddings(raw_image)

    # No prompts
    masks, scores = sam.get_masks(raw_image, image_embeddings=image_embeddings)
    geojson = sam.raster_to_vector(masks, scores, img_transform, filename="/tmp/masks_no.geojson")

    # Single points
    masks, scores = sam.get_masks(raw_image, image_embeddings=image_embeddings, input_points=input_points)
    geojson = sam.raster_to_vector(masks, scores, img_transform, filename="/tmp/masks_point.geojson")

    # Multiple points, and one point one (set of) mask
    masks, scores = sam.get_masks(raw_image, image_embeddings=image_embeddings, input_points=multiple_points)
    geojson = sam.raster_to_vector(masks, scores, img_transform, filename="/tmp/masks_multipoint.geojson")

    # Single bounding box
    masks, scores = sam.get_masks(raw_image, image_embeddings=image_embeddings, input_boxes=input_boxes)
    geojson = sam.raster_to_vector(masks, scores, img_transform, filename="/tmp/masks_bbox.geojson")

    # Bounding box and point with label 0 to mask out parts of the image
    masks, scores = sam.get_masks(raw_image, image_embeddings=image_embeddings, input_points=input_points, input_boxes=input_boxes, input_labels=input_labels, multimask_output=True)
    geojson = sam.raster_to_vector(masks, scores, img_transform, filename="/tmp/masks_point_bbox.geojson")

    # Multiple boxes and one set of masks for each box
    masks, scores = sam.get_masks(raw_image, image_embeddings=image_embeddings, input_boxes=multiple_boxes)
    geojson = sam.raster_to_vector(masks, scores, img_transform, filename="/tmp/masks_multibbox.geojson")