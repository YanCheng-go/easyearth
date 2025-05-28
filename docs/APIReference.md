# API Reference for EasyEarth
# From sawgger ui
#
# This document provides an overview of the API endpoints available in the EasyEarth project.
# It includes details on how to use the endpoints, the expected request and response formats, and examples of usage.
#
# ## API Endpoints
- /ping
  - **Method**: GET
  - **Description**: Check if the server is running.
  - **Response**: Returns a simple message indicating the server status.
  - **Example**:
    ```bash
    curl http://localhost:3781/v1/easyearth/ping
    ```
    ```json
    {
      "message": "EasyEarth server is running"
    }
    ```
- /predict
  - **Method**: POST
  - **Description**: Perform a prediction using a specified model.
  - **Request Body**:
    ```json
    {
      "model_type": "string",  // Type of model (e.g., "sam", "segment")
      "image_path": "string",  // Path to the input image
      "embedding_path": "string", // Optional, path to embedding file for SAM
      "model_path": "string",   // Path or identifier for the model
      "prompts": [              // Optional, list of prompts for SAM
        {
          "type": "Point",     // Type of prompt (e.g., "Point")
          "data": {
            "points": [[x, y]]  // Coordinates for the point prompt
          }
        }
      ]
    }
    ```
    - **Response**: Returns the prediction results.
    - **Example**:
    ```bash
    curl -X POST http://localhost:3781/v1/easyearth/predict \
    -H "Content-Type: application/json" \
    -d '{
      "model_type": "sam",
      "image_path": "/path/to/image.jpg",
      "embedding_path": "/path/to/embedding.pt",
      "model_path": "facebook/sam-vit-large",
      "prompts": [{
        "type": "Point",
        "data": {
          "points": [[850, 1100]]
        }
      }]
    }'
    ```
    ```json
    {
      "result": "Prediction result here"
    }
    ```

