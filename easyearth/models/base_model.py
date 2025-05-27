"""Base class for segmentation models"""

import torch
from PIL import Image
import numpy as np
import geopandas as gpd
from rasterio import features
import logging
from typing import Optional, Union, List, Dict, Any
from pathlib import Path
import os 
from datetime import datetime
import warnings
import torch.backends.mps

class BaseModel:
    def __init__(self, model_path: str, log_dir: Optional[str] = None):
        """Initialize base segmentation model
        Args:
            model_path: Path or name of the model to load
            log_dir: Directory to save log files (default: ./logs)
        """
        self.model_path = model_path
        self._setup_logging(log_dir)
        
        # Set CUDA device before any other CUDA operations
        self._setup_cuda()
        self.device = self._get_device()

        # Get environment variables from docker container
        self.cache_dir = os.environ.get('MODEL_CACHE_DIR', '~/.cache/huggingface/hub')

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
    
    def _setup_logging(self, log_dir: Optional[str] = None):
        """Setup logging configuration
        Args:
            log_dir: Directory to save log files
        """
        # Create logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Define log directory
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), 'logs')
            os.makedirs(log_dir, exist_ok=True)
        
        # Create log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"easyearth_model_{timestamp}.log")

        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to logger
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

        self.logger.info(f"Logging to: {log_file}")


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

        geojson = [
            {"properties": {"uid": value}, "geometry": polygon}
            for polygon, value in shape_generator
        ]

        if filename:
            # save geojson as .geojson file
            gdf = gpd.GeoDataFrame.from_features(geojson)
            gdf.to_file(filename=filename, driver="GeoJSON")

        return geojson

    def get_masks(self, image: Union[str, Path, Image.Image, np.array]):
        """Get masks for input image - to be implemented by child classes
        Args:
            image: The input image
        """
        raise NotImplementedError