from flask import request, jsonify
import numpy as np
import rasterio
import torch

from easyearth.models.langsam import SamText
from easyearth.models.sam import Sam
from easyearth.models.easy_sam2 import SAM2
from easyearth.models.segmentation import Segmentation
from PIL import Image
import requests
import os
import json
from datetime import datetime
import logging

logger = logging.getLogger("easyearth")

def verify_image_path(image_path):
    """Verify the image path and check if it is a valid URL or local file. Remember to convert the image path the path in the docker container"""
    # TODO: to complete
    if image_path.startswith(('http://', 'https://')):
        # Handle URL images
        try:
            response = requests.get(image_path, stream=True)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image from URL: {str(e)}")
            return False
    else:
        # Handle local files
        if os.path.isfile(image_path):
            return True
        else:
            logger.error(f"Invalid image path: {image_path}")
            return False

def verify_model_path(model_path):
    """"Verify the model path and check if it is a valid model path from hugging face"""
    # TODO: to complete
    raise NotImplementedError("Model path verification is not implemented yet.")


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

def reorganize_prompts(prompts):
    """
    Reorganize prompts into a unified format for processing.
    This function takes a list of prompts and organizes them into a dictionary with keys for points, labels, boxes, and text.
    Args:
        prompts: List of prompt dictionaries, where each dictionary contains:
            - 'type': Type of prompt (e.g., 'Point', 'Box', 'Text')
            - 'data': Dictionary containing the actual prompt data, which may include:
                - 'points': List of points for 'Point' prompts
                - 'labels': List of labels for 'Point' prompts
                - 'boxes': List of bounding boxes for 'Box' prompts
                - 'text': List of text prompts for 'Text' prompts
    Returns:
        dict: A dictionary with keys 'points', 'labels', 'boxes', and 'text', each containing a list of corresponding data.
        If no prompts of a certain type are provided, the corresponding list will be empty.
            - text: one dimensional list of text prompts
            - points: three dimensional list of points, where each point is a list of [x, y] coordinates
            - labels: one dimensional list of labels corresponding to the points
            - boxes: two dimensional list of bounding boxes, where each box is a list of [x1, y1, x2, y2] coordinates
    """
    transformed_prompts = {'points': [], 'labels': [], 'boxes': [], 'text': []}

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

# --- Unified predict endpoint ---

def predict():
    logger.debug("Starting unified prediction")

    try:
        data = request.get_json()
        model_type = data.get('model_type', 'sam')  # 'sam' or 'segment'
        image_path = data.get('image_path')
        model_path = data.get('model_path')
        TEMP_DIR = os.path.join(os.environ['BASE_DIR'], 'tmp')
        EMBEDDINGS_DIR = os.path.join(os.environ['BASE_DIR'], 'embeddings')

        if not image_path or not verify_image_path(image_path):
            return jsonify({'status': 'error', 'message': 'Invalid or missing image_path'}), 400

        # Load image
        try:
            if image_path.startswith(('http://', 'https://')):
                response = requests.get(image_path, stream=True)
                response.raise_for_status()
                image = Image.open(response.raw).convert('RGB')
                image_array = np.array(image)
                transform = None
                source_crs = None
            else:
                try:
                    with rasterio.open(image_path) as src:
                        transform = src.transform
                        source_crs = src.crs.to_string() if src.crs else None
                        image_array = src.read()
                        image_array = np.transpose(image_array, (1, 2, 0))
                except rasterio.errors.RasterioIOError:
                    image = Image.open(image_path).convert('RGB')
                    image_array = np.array(image)
                    transform = None
                    source_crs = None
            if len(image_array.shape) == 2:
                image_array = np.stack([image_array] * 3, axis=-1)
            elif image_array.shape[2] > 3:
                image_array = image_array[:, :, :3]
        except Exception as e:
            logger.error("Error loading image", exc_info=True)
            return jsonify({'status': 'error', 'message': f'Failed to load image: {str(e)}'}), 500

        original_height, original_width = image_array.shape[:2]

        # --- LangSam branch ---
        if model_type == 'langsam':
            prompts = data.get('prompts', [])
            transformed_prompts = reorganize_prompts(prompts)
            input_text = transformed_prompts.get('text')
            # get one dimensional list of text prompts
            if len(input_text) > 0 and isinstance(input_text[0], list):
                input_text = [text for sublist in input_text for text in sublist]

            # Initialize LangSam
            logger.info("Initializing LangSam model")
            langsam = SamText(model_path or 'ultralytics/sam2.1_s')

            # Get masks from LangSam
            masks_path, _ = langsam.get_masks(image_path, input_text=input_text)

            if masks_path is None or len(masks_path) == 0:
                return jsonify({'status': 'error', 'message': 'No valid masks generated'}), 400

            # Convert masks to GeoJSON
            geojson_path = f"{TEMP_DIR}/predict-langsam_{os.path.basename(image_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            geojson = langsam.raster_to_vector(masks_path[0], input_text[0], filename=geojson_path, img_transform=transform)

        # --- SAM2 branch ---
        elif model_type == 'sam2' and model_path.startswith('ultralytics/sam2'):
            prompts = data.get('prompts', [])
            transformed_prompts = reorganize_prompts(prompts)

            # Initialize SAM2
            logger.debug("Initializing SAM2 model")
            sam2 = SAM2(model_path or 'ultralytics/sam2.1_b')

            # Get masks from SAM2
            masks = sam2.get_masks(
                image_array,
                bboxes=transformed_prompts['boxes'] if len(transformed_prompts['boxes']) > 0 else None,
                points=transformed_prompts['points'] if len(transformed_prompts['points']) > 0 else None,
                labels=transformed_prompts['labels'] if len(transformed_prompts['labels']) > 0 else None,
            )

            if masks is None:
                return jsonify({'status': 'error', 'message': 'No valid masks generated'}), 400

            # Convert masks to GeoJSON
            geojson_path = f"{TEMP_DIR}/predict-sam2_{os.path.basename(image_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            geojson = sam2.raster_to_vector(masks, transform, filename=geojson_path)

        # --- SAM branch ---
        elif model_type == 'sam' and model_path.startswith('facebook/sam-'):
            prompts = data.get('prompts', [])
            transformed_prompts = reorganize_prompts(prompts)

            # Handle embeddings
            embedding_path = data.get('embedding_path', None)
            save_embeddings = data.get('save_embeddings', False)

            # Initialize SAM
            logger.debug("Initializing SAM model")
            sam = Sam(model_path or 'facebook/sam-vit-base')

            image_embeddings = None

            if embedding_path and os.path.exists(embedding_path) and not save_embeddings:
                try:
                    logger.debug(f"Loading image embeddings from: {embedding_path}")
                    embedding_data = torch.load(embedding_path)

                    # handle different formats of embedding data
                    if isinstance(embedding_data, dict):
                        if embedding_data.get('image_shape') == image_array.shape[:2]:
                            image_embeddings = embedding_data['embeddings'].to(sam.device)
                            used_cache = True
                        else:
                            logger.warning("Unexpected format in embedding data, using SAM to generate embeddings")
                    else:
                        image_embeddings = embedding_data.to(sam.device)
                        used_cache = True

                except Exception as e:
                    image_embeddings = None

            # Generate embeddings if not loaded from cache
            else:
                logger.debug("Generating image embeddings without caching.")
                image_embeddings = sam.get_image_embeddings(image_array)

                # generate an index file to relate image to the embeddings
                index_path = os.path.join(EMBEDDINGS_DIR, 'index.json')

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
                        embedding_data = {
                            'embeddings': image_embeddings.cpu(),
                            'image_shape': image_array.shape[:2],
                            'timestamp': datetime.now().isoformat()
                        }
                        logger.debug(f"Saving image embeddings to: {embedding_path}")
                        torch.save(embedding_data, embedding_path)
                    except Exception as e:
                        logger.error(f"Failed to save image embeddings: {str(e)}")
                        return jsonify({'status': 'error', 'message': f'Failed to save image embeddings: {str(e)}'}), 500

            # Get masks from SAM
            masks, scores = sam.get_masks(
                image_array,
                image_embeddings=image_embeddings,
                input_points=transformed_prompts['points'] if len(transformed_prompts['points']) > 0 else None,
                input_labels=transformed_prompts['labels'] if len(transformed_prompts['labels']) > 0 else None,
                input_boxes=transformed_prompts['boxes'] if len(transformed_prompts['boxes']) > 0 else None,
            )

            if masks is None:
                return jsonify({'status': 'error', 'message': 'No valid masks generated'}), 400

            # Convert masks to GeoJSON
            geojson_path = f"{TEMP_DIR}/predict-sam_{os.path.basename(image_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            geojson = sam.raster_to_vector(masks, scores, transform, filename=geojson_path)

        # --- Segmentation branch ---
        elif model_type == 'segment':
            # Initialize Segmentation model
            logger.debug("Initializing Segmentation model")
            segformer = Segmentation(model_path or 'restor/tcd-segformer-mit-b5')

            aoi = data.get('aoi', None)
            if aoi:
                image_array = segformer.focus_on_region(image_array, aoi["coordinates"])

            # Get masks from Segmentation model
            masks = segformer.get_masks(image_array)

            # If the image is cropped, we need to reproject the masks back to the original image size
            if aoi and len(aoi) > 0 and isinstance(aoi["coordinates"], list) and len(aoi["coordinates"]) == 4:
                if isinstance(masks, list):
                    masks = masks[0]  # Get the first mask if multiple masks are returned
                # Create an empty canvas the size of the original image
                if isinstance(masks, torch.Tensor):
                    pseudo_image = torch.zeros((original_height, original_width), dtype=masks.dtype)
                else:
                    pseudo_image = np.zeros((original_height, original_width), dtype=masks.dtype)

                x_min, y_min, x_max, y_max = aoi["coordinates"]
                pseudo_image[y_min:y_max, x_min:x_max] = masks

                # Wrap in a list to match expected format
                masks = [pseudo_image]

            if masks is None:
                return jsonify({'status': 'error', 'message': 'No valid masks generated'}), 400

            # Convert masks to GeoJSON
            geojson_path = f"{TEMP_DIR}/predict-segment_{os.path.basename(image_path)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            geojson = segformer.raster_to_vector(masks, transform, filename=geojson_path)

        else:
            return jsonify({'status': 'error', 'message': f'Unknown model_type: {model_type}'}), 400

        return jsonify({'status': 'success', 'features': geojson, 'crs': source_crs}), 200

    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Server error: {str(e)}'}), 500

def ping():
    """Endpoint to check if the server is alive", and to check GPU availability"""
    gpu_info = {
        "CUDA": torch.cuda.is_available(),
        "MPS": getattr(torch.backends, "mps", None) and torch.backends.mps.is_available(),
        "CPU": not torch.cuda.is_available() and not (getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
    }

    gpu_info["device"] = "CUDA" if gpu_info["CUDA"] else "MPS" if gpu_info["MPS"] else "CPU"

    return jsonify({"message": "Server is alive",
                    "device": gpu_info["device"],
                    "user_base_dir": os.environ.get("USER_BASE_DIR"),
                    "run_mode": os.environ.get("RUN_MODE")}), 200
