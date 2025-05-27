from flask import request, jsonify
import numpy as np
import rasterio
from easyearth.models.segmentation import Segmentation
from PIL import Image
import requests
import os
import logging
import json
from datetime import datetime
import sys
try:
    from .predict_controller import verify_image_path, verify_model_path, setup_logging
except ImportError:
    # For direct script execution
    from predict_controller import verify_image_path, verify_model_path, setup_logging

def predict():
    """Handle prediction request for segmentation models from hugging face."""
    # Set up logging
    logger = setup_logging(name="segment-controller")
    logger.debug("Starting Segmentation prediction")

    try:
        # Get the image data from the request
        data = request.get_json()

        # get env variable DATA_DIR from the docker container
        TEMP_DIR = os.environ.get('EASYEARTH_TEMP_DIR')

        # Validate and convert image path
        image_path = data.get('image_path')
        if not image_path:
            return jsonify({
                'status': 'error',
                'message': 'image_path is required'
            }), 400
        # Verify image path
        else:
            if not verify_image_path(image_path):
                return jsonify({
                    'status': 'error',
                    'message': f'Invalid image path: {image_path}'
                }), 408

        # Get model path and warmup
        model_path = data.get('model_path', 'restor/tcd-segformer-mit-b5')
        if not model_path:
            return jsonify({
                'status': 'error',
                'message': 'model_path is required'
            }), 400
        # # Verify model path
        # else:
        #     if not verify_model_path(model_path):
        #         return jsonify({
        #             'status': 'error',
        #             'message': f'Invalid model path: {model_path}'
        #         }), 408

        # # TODO: add warmup the model
        # segformer = Segmentation(model_path)
        # logger.debug("Warming up model")
        #
        # # create a random input tensor to warm up the model, shape 1024x1024x3
        # segformer.get_masks(np.zeros((1, 3, 512, 512)))  # Dummy input for warmup
        # logger.debug(f"Model warmup completed: {model_path}")

        # Load image with detailed error handling
        try:
            if image_path.startswith(('http://', 'https://')):
                # Handle URL images
                response = requests.get(image_path, stream=True)
                response.raise_for_status()
                image = Image.open(response.raw).convert('RGB')
                image_array = np.array(image)
                transform = None
                source_crs = None
            try:
                with rasterio.open(image_path) as src:
                    transform = src.transform
                    source_crs = src.crs.to_string() if src.crs else None
                    image_array = src.read()
                    image_array = np.transpose(image_array, (1, 2, 0))
            except rasterio.errors.RasterioIOError:
                # Not a rasterio-compatible file, handle as a regular image
                logger.debug(f"Loading local image from: {image_path}")
                image = Image.open(image_path).convert('RGB')
                image_array = np.array(image)
                transform = None
                source_crs = None

            # Ensure image is in the correct format
            if len(image_array.shape) == 2:
                image_array = np.stack([image_array] * 3, axis=-1)
            elif image_array.shape[2] > 3:
                image_array = image_array[:, :, :3]

        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image from URL: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to download image: {str(e)}'
            }), 500
        except Exception as e:
            logger.error("Error loading image:", exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Failed to load image: {str(e)}'
            }), 500

        try:
            # Initialize SAM
            logger.debug("Initializing Segmentation model")
            segformer = Segmentation(model_path)

            # Get masks
            masks = segformer.get_masks(image_array)

            if masks is None:
                return jsonify({
                    'status': 'error',
                    'message': 'No valid masks generated'
                }), 400

            geojson_path = f"{TEMP_DIR}/predict-segment_{os.path.basename(image_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            # Convert to GeoJSON
            geojson = segformer.raster_to_vector(
                masks,
                transform,
                filename=geojson_path
            )

            return jsonify({
                'status': 'success',
                'features': geojson,
                'crs': source_crs
            }), 200

        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Prediction error: {str(e)}'
            }), 500

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Server error: {str(e)}'
        }), 500