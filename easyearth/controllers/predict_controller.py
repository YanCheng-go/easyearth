import logging
import os
import sys
from datetime import datetime
from easyearth.config.log_config import setup_logger

logger = setup_logger(name="predict-controller")

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


def generate_random_predictions():
    types = ["Class", "Points", "Polygons"]
    predictions = []
    for _ in range(random.randint(1, 5)):  # Random number of predictions
        prediction_type = random.choice(types)
        if prediction_type == "Class":
            predictions.append({"type": "Class", "data": {"label": "example_class", "confidence": random.random()}})
        elif prediction_type == "Points":
            predictions.append({"type": "Points", "data": [{"x": random.randint(0, 100), "y": random.randint(0, 100)} for _ in range(random.randint(1, 5))]})
        elif prediction_type == "Polygons":
            predictions.append({"type": "Polygons", "data": [[{"x": random.randint(0, 100), "y": random.randint(0, 100)} for _ in range(4)] for _ in range(random.randint(1, 3))]})
    return predictions

def predict():
    response = {
        "model_description": "Mock Image Analysis Model v1.0",
        "predictions": generate_random_predictions()
    }
    return jsonify(response), 200

def ping():
    return jsonify({"message": "Server is alive"}), 200