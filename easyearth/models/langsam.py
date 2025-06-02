"""SAM with text prompts for Earth Observation tasks.
reference: https://samgeo.gishub.org/examples/text_prompts/"""
import datetime
import os
from pathlib import Path
from typing import Union, List, Optional, Any, Dict

import PIL
import numpy as np
import torch
from PIL import Image
from samgeo.text_sam import LangSAM
from collections import defaultdict
from rasterio import features
import shapely.geometry
import geopandas as gpd
import rasterio

try:
    from .base_model import BaseModel
except ImportError:
    # For direct script execution
    from base_model import BaseModel

# TODO: customize the LangSAM class to fit the overall model script structure
class SamText(BaseModel):
    map_model_path = {
        'facebook/sam-vit-b': 'vit_b',
        'facebook/sam-vit-l': 'vit_l',
        'facebook/sam-vit-h': 'vit_h',
        'ultralytics/sam2.1_t': 'sam2-hiera-tiny',
        'ultralytics/sam2.1_s': 'sam2-hiera-small',
        'ultralytics/sam2.1_b': 'sam2-hiera-base-plus',
        'ultralytics/sam2.1_l': 'sam2-hiera-large',
    }
    def __init__(self, model_path: str = "sam2-hiera-small"):
        """Initialize the LangSAM model."""
        super().__init__(model_path)
        self.model_path = SamText.map_model_path.get(model_path, 'vit_b')
        self.model = LangSAM(self.model_path)
    #
    # def get_masks(self, image_path: Union[str, PIL.Image.Image], input_text: List[str]) -> tuple:
    #     """
    #     Get masks for the given image using text prompts.
    #     Args:
    #         image_path (str): Path to the image file.
    #         input_text (List[str]): List of text prompts to guide the mask generation.
    #     Returns:
    #         tuple: A tuple containing masks, boxes, phrases, and logits.
    #     """
    #     if not input_text:
    #         self.logger.warning("Input text list is empty. Returning empty results.")
    #         return None, None, None, None
    #
    #     for text in input_text:
    #         if not isinstance(text, str):
    #             raise ValueError(f"Input text must be a string, got {type(text)} instead.")
    #
    #     self.logger.info(f"Processing image: {image_path} with text prompts: {input_text}")
    #
    #     masks, boxes, texts, logits = [], [], [], []
    #
    #     for text in input_text:
    #         results = self.model.predict(image_path, text, box_threshold=0.24, text_threshold=0.24, return_results=True)
    #         # move results to CPU if they are on GPU
    #         if isinstance(results, tuple):
    #             results = [res.cpu() if isinstance(res, torch.Tensor) else res for res in results]
    #         # Extract the shape of the mask scores/logits
    #         n_mask = results[3].shape[0] if isinstance(results[3], np.ndarray) else len(results[3])
    #         # Select the highest scoring mask
    #         if n_mask > 1:
    #             max_index = torch.argmax(results[3]).item() if isinstance(results[3], torch.Tensor) else np.argmax(
    #                 results[3])
    #             self.logger.info(f"Selected mask index: {max_index} with score: {results[3][max_index]}")
    #         else:
    #             max_index = 0
    #             self.logger.info(f"Only one mask available, using index: {max_index} with score: {results[3][max_index]}")
    #         # Append the selected mask, box, text, and logits
    #         masks.append(results[0][max_index, :, :])
    #         boxes.append(results[1][max_index])
    #         texts.append(results[2][max_index])
    #         logits.append(results[3][max_index])
    #
    #     # Stack list of tensors/arrays into a single tensor/array
    #     if isinstance(masks[0], torch.Tensor):
    #         masks = torch.stack(masks, dim=0)
    #     elif isinstance(masks[0], np.ndarray):
    #         masks = np.stack(masks, axis=0)
    #     else:
    #         raise ValueError("Masks should be either torch.Tensor or np.ndarray")
    #
    #     # Ensure 3D shape: (Objects, Height, Width)
    #     if masks.ndim == 2:
    #         masks = masks[np.newaxis, :, :]
    #     if masks.ndim != 3:
    #         self.logger.warning(f"Unexpected masks shape: {masks.shape}. Expected 2D or 3D array, got {masks.ndim}D.")
    #
    #     return [masks], boxes, texts, logits
    #
    # def raster_to_vector(self,masks: List[np.ndarray], logits: List[float], texts: List[str], img_transform=None,
    #                      filename: Optional[str] = None) -> List[Dict[str, Any]]:
    #     """
    #     Converts raster masks to vector format (GeoJSON).
    #     Args:
    #         masks (List[np.ndarray]): List of masks as numpy arrays.
    #         logits (List[float]): List of logits corresponding to the masks.
    #         texts (List[str]): List of phrases corresponding to the masks.
    #         img_transform: Optional transformation for georeferencing.
    #         filename (Optional[str]): If provided, saves the GeoJSON to this file.
    #     Returns:
    #         GeoJSON features as a list of dictionaries.
    #     """
    #
    #     masks_combined = masks[0]
    #     if masks[0].shape[0] > 1:
    #         # Replace the pixel value with the index of the first dimension + 1
    #         objects_id = torch.arange(masks[0].shape[0]).view(-1, 1, 1).expand_as(masks[0])  # the first dimension is the object id
    #         masks_id = torch.where(masks[0], objects_id + 1, torch.tensor(0))  # the second dimension is the mask id, one object may have multiple predicted masks with different confidence scores
    #         masks_combined = torch.amax(masks_id, dim=0, keepdim=False).numpy().astype(np.uint8) # Combine masks by taking the maximum across the first dimension, so the latter objects overwrite the former
    #
    #     geojson = super().raster_to_vector([masks_combined], img_transform, filename=None)
    #
    #     # If no features, append an empty polygon with default properties
    #     if not geojson or len(geojson) == 0:
    #         self.logger.warning("No masks found, returning empty GeoJSON.")
    #         geojson.append({
    #             "properties": {"uid": 0, "score": 0, "text": ""},
    #             "geometry": {"type": "Polygon", "coordinates": []}
    #         })
    #     else:
    #         # Add logits as property for each feature
    #         for i, feature in enumerate(geojson):
    #             # Safeguard against index error
    #             feature['properties']['score'] = logits[i].item() if isinstance(logits[i], torch.Tensor) else logits[i]
    #             feature['properties']['text'] = texts[i]
    #
    #     # Save to file if requested
    #     if filename:
    #         import geopandas as gpd
    #         gdf = gpd.GeoDataFrame.from_features(geojson)
    #         gdf.to_file(filename, driver='GeoJSON')
    #
    #     return geojson

    def get_masks(self, image_path: Union[str, PIL.Image.Image], input_text: List[str]):
        """
        Get masks for the given image using text prompts.
        Args:
            image_path: (Union[str, PIL.Image]): Path to the image file or a PIL Image object.
            input_text: (List[str]): List of text prompts to guide the mask generation.
        Returns:
            tuple: A tuple containing mask paths and input text.
        """
        mask_paths = []
        for text in input_text:
            if not isinstance(text, str):
                raise ValueError(f"Input text must be a string, got {type(text)} instead.")
            timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d_%H%M%S')
            output_path = os.path.join(self.tmp_dir, f"sam-text_{text}_{timestamp}.tif")
            self.logger.info(f"Processing image: {image_path} with text prompt: {text}")
            self.model.predict(image_path, text, box_threshold=0.24, text_threshold=0.24,
                               return_results=False, output=output_path, mask_multiplier=1)
            mask_paths.append(output_path)
        return mask_paths, input_text

    def raster_to_vector(self, masks_path, text, filename, img_transform):
        """Vectorize a raster dataset.
        Args:
            masks_path (str): Path to the raster mask file.
            text (str): Text prompt used for generating the masks.
            filename (Optional[str]): If provided, saves the GeoJSON to this file.
            img_transform: Optional transformation for georeferencing.
        Returns:
            List[Dict[str, Any]]: GeoJSON features as a list of dictionaries.
        """
        # TODO: adapt to support multiple masks
        with rasterio.open(masks_path) as src:
            band = src.read()

            mask = band != 0
            shape_generator = features.shapes(band, mask=mask, transform=img_transform)

        label_to_polygons = defaultdict(list)
        for polygon, value in shape_generator:
            label_to_polygons[value].append(shapely.geometry.shape(polygon))

        geojson = []
        for value, polygons in label_to_polygons.items():
            if len(polygons) == 1:
                geometry = shapely.geometry.mapping(polygons[0])
            else:
                # If there are multiple polygons, create a MultiPolygon
                multipolygon = shapely.geometry.MultiPolygon([p for p in polygons])
                geometry = shapely.geometry.mapping(multipolygon)
            geojson.append({"properties": {"uid": value}, "geometry": geometry})

        # Fallback in case no geometries were found
        if len(geojson) == 0:
            self.logger.warning("No polygons found; creating empty fallback GeoJSON.")
            empty_geom = shapely.geometry.mapping(shapely.geometry.MultiPolygon([]))
            geojson.append({
                "properties": {"uid": -1},
                "geometry": empty_geom
            })

        # Add text prompt to properties
        for feature in geojson:
            feature['properties']['text'] = text

        if filename:
            gdf = gpd.GeoDataFrame.from_features(geojson)
            gdf.to_file(filename=filename, driver="GeoJSON")

        return geojson

if __name__ == '__main__':
    sam_text = SamText(model_path="facebook/sam-vit-b")
    image_path = "/home/yan/Downloads/easyearth_data/easyearth_base/images/sam_text.tif"
    text_prompt = ["tree"]  # Example text prompts

    # results = LangSAM().predict(image_path, text_prompt[0], box_threshold=0.24, text_threshold=0.24, return_results=True, output="/tmp/masks.tif")
    # LangSAM().raster_to_vector('/tmp/masks.tif', '/tmp/masks_sam_text.geojson')

    # get image transform info
    try:
        with rasterio.open(image_path) as src:
            img_transform = src.transform
    except Exception as e:
        print(f"Error reading image transform: {e}")
        img_transform = None

    masks, texts = sam_text.get_masks(image_path, text_prompt)
    geojson = sam_text.raster_to_vector(masks[0], texts[0], filename='/tmp/masks_sam_text.geojson',
                                        img_transform=img_transform)