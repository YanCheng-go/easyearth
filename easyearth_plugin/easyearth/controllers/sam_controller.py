from flask import Flask, request, jsonify
import numpy as np
import rasterio
import torch  # Add this for CRS transformation
from easyearth.models.sam import Sam
from PIL import Image
import requests
import os
import logging
import json
from datetime import datetime
import sys
try:
    from .predict_controller import verify_image_path, verify_model_path
except ImportError:
    # For direct script execution
    from predict_controller import verify_image_path, verify_model_path

# Create logs directory in the plugin directory
PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(PLUGIN_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Set up logging configuration
log_file = os.path.join(LOG_DIR, f'sam_controller_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='a'),  # 'a' for append mode
        logging.StreamHandler(sys.stdout)  # This will print to Docker logs
    ]
)

# Get logger for this module
logger = logging.getLogger(__name__)

# Log some initial information
logger.info(f"=== Server Starting ===")
logger.info(f"Plugin directory: {PLUGIN_DIR}")
logger.info(f"Log directory: {LOG_DIR}")
logger.info(f"Log file: {log_file}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Python path: {sys.path}")

# Test logging
logger.debug("Debug message test")
logger.info("Info message test")
logger.warning("Warning message test")

def reorganize_prompts(prompts):
    """
    Reorganize prompts into a dictionary with separate lists for points, labels, boxes, and text

    Args:
        prompts (list): List of prompt dictionaries
    Returns:
        transformed_prompts (dict): Dictionary with separate lists for points, labels, boxes, and text, each object with the dimension of (batch, number of objectsm, dimention of each object) with the batch dimention as 1
    """

    transformed_prompts = {
        'points': [],
        'labels': [],
        'boxes': [],
        'text': []
    }

    for prompt in prompts:
        prompt_type = prompt.get('type')
        prompt_data = prompt.get('data', {})
        if prompt_type == 'Point':
            transformed_prompts['points'].append(prompt_data.get('points', []))
            transformed_prompts['labels'].extend(prompt_data.get('labels', []))
        elif prompt_type == 'Box':
            transformed_prompts['boxes'].extend(prompt_data.get('boxes', []))
        elif prompt_type == 'Text':
            transformed_prompts['text'].extend(prompt_data.get('text', []))

    for key in ['points', 'labels', 'boxes', 'text']:
        if len(transformed_prompts[key]) > 0:
            transformed_prompts[key] = [transformed_prompts[key]]
    if len(transformed_prompts['points']) > 0:
        if np.array(transformed_prompts['points']).shape[1] == 1:
            transformed_prompts['points'] = transformed_prompts['points'][0]

    return transformed_prompts

# TODO: add this to the predict function
def reproject_prompts(prompts, transform, image_shape):
    """
    Transform all types of prompts from map coordinates to pixel coordinates

    Args:
        prompts (list): List of prompt dictionaries
        transform (affine.Affine): Rasterio transform object
        image_shape (tuple): Image dimensions (height, width)
    """

    height, width = image_shape[:2]

    def clip_coordinates(x, y):
        """Clip coordinates to image boundaries"""
        x = max(0, min(int(x), width - 1))
        y = max(0, min(int(y), height - 1))
        return x, y

    input_points = prompts.get('points', [])
    input_labels = prompts.get('labels', [])
    input_boxes = prompts.get('boxes', [])
    input_text = prompts.get('text', [])

    transformed = {
        'points': [],
        'labels': [],
        'boxes': [],
        'text': []
    }

    if input_points:
        for point in input_points:
            px, py = ~transform * (point[0], point[1])
            px, py = clip_coordinates(px, py)
            transformed['points'].append([px, py])

        transformed['labels'].extend(input_labels)

    if input_boxes:
        for box in input_boxes:
            x1, y1 = ~transform * (box[0], box[1])
            x2, y2 = ~transform * (box[2], box[3])

            x1, y1 = clip_coordinates(x1, y1)
            x2, y2 = clip_coordinates(x2, y2)

            transformed['boxes'].append([
                min(x1, x2),
                min(y1, y2),
                max(x1, x2),
                max(y1, y2)
            ])

    if input_text:
        transformed['text'].extend(input_text)

    return transformed

def predict():
    """Handle prediction request with improved embedding handling"""
    try:
        # Get the image data from the request
        data = request.get_json()

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

        # Get model path and warm up
        model_path = data.get('model_path', 'facebook/sam-vit-base')
        if not model_path:
            return jsonify({
                'status': 'error',
                'message': 'model_path is required'
            }), 408
        # Verify model path
        # else:
        #     if not verify_model_path(model_path):
        #         return jsonify({
        #             'status': 'error',
        #             'message': f'Invalid model path: {model_path}'
        #         }), 408

        # Warm up the model
        logger.debug(f"Warmup model: {model_path}")
        sam = Sam(model_path)
        # create a random input tensor to warm up the model, shape 1024x1024x3
        sam.get_masks(np.zeros((1, 3, 512, 512)))  # Dummy input for warmup
        logger.debug(f"Model warmup completed: {model_path}")

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
            elif image_path.endswith('.tif'):
                # Handle local GeoTIFF files
                with rasterio.open(image_path) as src:
                    transform = src.transform
                    source_crs = src.crs.to_string()
                    image_array = src.read()
                    image_array = np.transpose(image_array, (1, 2, 0))
            else:
                # Handle local regular images
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

        # Process prompts
        try:
            prompts = data.get('prompts', [])
            transformed_prompts = reorganize_prompts(prompts)
            
            # Initialize SAM
            logger.debug("Initializing SAM model")
            sam = Sam(model_path)

            # Handle embeddings
            embedding_path = data.get('embedding_path')
            save_embeddings = data.get('save_embeddings', False)
            
            image_embeddings = None

            if embedding_path and os.path.exists(embedding_path):
                try:
                    logger.debug(f"Loading cached embedding from: {embedding_path}")
                    embedding_data = torch.load(embedding_path)
                    
                    # Handle both old and new format embeddings
                    if isinstance(embedding_data, dict):
                        # New format with metadata
                        if embedding_data.get('image_shape') == image_array.shape[:2]:
                            image_embeddings = embedding_data['embeddings'].to(sam.device)
                            used_cache = True
                        else:
                            logger.warning("Cached embedding shape mismatch, will generate new one")
                    else:
                        # Old format - direct embeddings
                        image_embeddings = embedding_data.to(sam.device)
                        used_cache = True
                        
                except Exception as e:
                    image_embeddings = None

            # Generate new embeddings if needed
            else:
                logger.info("Generating new embeddings")
                image_embeddings = sam.get_image_embeddings(image_array)

                # generate an index file to relate the image to the embedding
                # get env variable DATA_DIR
                DATA_DIR = os.environ.get('EASYEARTH_DATA_DIR')
                os.makedirs(os.path.join(DATA_DIR, 'embeddings'), exist_ok=True)
                index_path = os.path.join(DATA_DIR, 'embeddings', 'index.json')
                if os.path.exists(index_path):
                    with open(index_path, 'r') as f:
                        index = json.load(f)
                else:
                    index = {}
                
                # add the embedding path to the index
                index[image_path] = embedding_path
                with open(index_path, 'w') as f:
                    json.dump(index, f)
                
                if save_embeddings and embedding_path:
                    try:
                        os.makedirs(os.path.dirname(embedding_path), exist_ok=True)
                        # Save with metadata
                        embedding_data = {
                            'embeddings': image_embeddings.cpu(),
                            'image_shape': image_array.shape[:2],
                            'timestamp': datetime.now().isoformat()
                        }
                        torch.save(embedding_data, embedding_path)
                    except Exception as e:
                        logger.error(f"Failed to save embeddings: {str(e)}")

            # Get masks
            masks, scores = sam.get_masks(
                image_array,
                image_embeddings=image_embeddings,
                input_points=transformed_prompts['points'] if len(transformed_prompts['points'])>0 else None,
                input_labels=transformed_prompts['labels'] if len(transformed_prompts['labels'])>0 else None,
                input_boxes=transformed_prompts['boxes'] if len(transformed_prompts['boxes'])>0 else None,
            )

            if masks is None:
                return jsonify({
                    'status': 'error',
                    'message': 'No valid masks generated'
                }), 400

            geojson_path = f"{PLUGIN_DIR}/tmp/predict-sam_{os.path.basename(image_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            os.makedirs(os.path.dirname(geojson_path), exist_ok=True)
            # Convert to GeoJSON
            geojson = sam.raster_to_vector(
                masks,
                scores,
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

#
# # test reorganize_prompts
# if __name__ == "__main__":
#     # Test reorganize_prompts function
#     test_prompts = [
#         {
#             'type': 'Point',
#             'data': {
#                 'points': [[850, 1100]],
#             }
#         }
#         ,
#         {
#             'type': 'Point',
#             'data': {
#                 'points': [[2250, 1000]],
#             }
#         }
#     ]
#
#     transformed_prompts = reorganize_prompts(test_prompts)
#
#     from easyearth_plugin.easyearth.models.sam import Sam
#     sam = Sam()
#     image_url = "https://huggingface.co/ybelkada/segment-anything/resolve/main/assets/car.png"
#     raw_image = Image.open(requests.get(image_url, stream=True).raw).convert("RGB")
#     img_transform = rasterio.transform.from_bounds(0, 0, 1024, 1024, 1024, 1024)
#     image_embeddings = sam.get_image_embeddings(raw_image)
#
#     # Test reproject_prompts function
#     masks, scores = sam.get_masks(
#         raw_image,
#         image_embeddings=image_embeddings,
#         input_points=transformed_prompts['points'] if len(transformed_prompts['points']) > 0 else None,
#         input_labels=transformed_prompts['labels'] if len(transformed_prompts['labels']) > 0 else None,
#         input_boxes=transformed_prompts['boxes'] if len(transformed_prompts['boxes']) > 0 else None,
#         multimask_output=True
#     )
#     # to vector
#     geojson = sam.raster_to_vector(masks, scores, img_transform,
#                                    filename="/home/yan/PycharmProjects/easyearth/easyearth_plugin/tmp/masks_multipoints.geojson")