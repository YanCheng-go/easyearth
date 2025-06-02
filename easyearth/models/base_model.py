"""Base class for segmentation models"""
from collections import defaultdict

import shapely
import torch
from PIL import Image
import numpy as np
import geopandas as gpd
from rasterio import features
import logging
from typing import Optional, Union, List, Dict, Any
from pathlib import Path
import os
import warnings
import torch.backends.mps

class BaseModel:
    def __init__(self, model_path: str):
        """Initialize base segmentation model
        Args:
            model_path: Path or name of the model to load
        """
        self.model_path = model_path
        self.logger = logging.getLogger("easyearth")
        
        # Set CUDA device before any other CUDA operations
        self._setup_cuda()
        self.device = self._get_device()

        # Get environment variables from docker container
        self.cache_dir = os.environ.get('MODEL_CACHE_DIR', os.path.join(os.path.expanduser("~"), ".cache", "easyearth", "models"))
        self.logger.info(f"Model cache directory: {self.cache_dir}")

    # TODO: figure out why GPU is not working on my computer
    def _setup_cuda(self):
        """Setup CUDA environment before initialization"""
        try:
            # Explicitly set CUDA_VISIBLE_DEVICES if not set
            if "CUDA_VISIBLE_DEVICES" not in os.environ:
                os.environ["CUDA_VISIBLE_DEVICES"] = "0"
            
            # Clear CUDA cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                
            self.logger.info(f"CUDA_VISIBLE_DEVICES: {os.environ.get('CUDA_VISIBLE_DEVICES', 'not set')}")
        except Exception as e:
            self.logger.warning(f"Error setting up CUDA: {str(e)}")

    def _get_device(self) -> torch.device:
        """Get the device to run the model on, with proper error handling"""
        try:
            # Check for MPS (Apple silicon GPU)
            if torch.backends.mps.is_available():
                mps_device = torch.device("mps")
                self.logger.info("Using MPS device")
                return mps_device
            else:
                self.logger.info("MPS device not available")

            # Suppress the specific CUDA warning
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="CUDA initialization: CUDA unknown error")
                
                if torch.cuda.is_available() and torch.cuda.device_count() > 0:
                    cuda_device = torch.device("cuda:0") # try to get the first available CUDA device
                    # Test if the device is actually available
                    torch.zeros((1,), device=cuda_device)
                    self.logger.info(f"Using CUDA device: {torch.cuda.get_device_name(0)}")
                    return cuda_device
                
        except Exception as e:
            self.logger.warning(f"CUDA device initialization failed: {str(e)}")
            self.logger.warning("Falling back to CPU")
        
        self.logger.info("Using CPU device")
        return torch.device("cpu")

    def raster_to_vector(self, 
                        masks: Union[List[np.ndarray], List[torch.Tensor]],
                        img_transform: Optional[Any] = None, 
                        filename: Optional[str] = None) -> List[Dict]:
        """Converts a raster mask to a vector mask
        Args:
            masks: predictions from the segmentation model in hugging face format
            img_transform: Optional transform for georeferencing
            filename: Optional filename (including directory path) to save GeoJSON
        Returns: 
            List of GeoJSON features
        """

        # TODO: need to test if this works for prediction for an entire image (segmentation.py)
        masks = masks[0]
        self.logger.debug(f"masks: {masks}")

        # convert tensor to numpy array
        if isinstance(masks, torch.Tensor):
            self.logger.debug(f"masks shape: {masks.shape}")
            masks = masks.cpu().numpy()
            masks = (masks > 0).astype(np.uint8)

        # squeeze the masks to remove singleton dimensions
        if masks.ndim > 2:
            masks = np.squeeze(masks, axis=0)

        if img_transform is not None:
            shape_generator = features.shapes(
                masks,
                mask=masks > 0,
                transform=img_transform,
            )
        else:
            shape_generator = features.shapes(
                masks,
                mask=masks > 0,
            )

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

        if filename:
            gdf = gpd.GeoDataFrame.from_features(geojson)
            gdf.to_file(filename=filename, driver="GeoJSON")

        return geojson

    def get_masks(self, image: Union[str, Path, Image.Image, np.array]):
        """Get masks for input image - to be implemented by child classes
        Args:
            image: The input image
        """
        raise NotImplementedError