EasyEarth Developer Guide
=========================
This guide provides instructions for developers to set up and run the EasyEarth server outside of QGIS, including how to use the model APIs.

## Build the Docker image
If you make changes to the code, you can rebuild the Docker image using:
```bash
cd easyearth  # go to the directory where docker-compose.yml is located
./setup.sh  # run the setup.sh script to rebuild the Docker image
```

## Start the Server
```bash
cd easyearth  # go to the directory where docker-compose.yml is located
./setup.sh  # remember to setup the data folder.
```

## ✨ Test server and model APIs
### 📍 Use SAM with Prompts

```bash
curl -X POST http://127.0.0.1:3781/v1/easyearth/predict \
-H "Content-Type: application/json" \
-d '{
  "model_type": "sam",
  "image_path": "/usr/src/app/data/DJI_0108.JPG",
  "embedding_path": "/usr/src/app/data/embeddings/DJI_0108.pt",
  "model_path": "facebook/sam-vit-large",
  "prompts": [{
    "type": "Point",
    "data": {
      "points": [[850, 1100]]
    }
  }]
}'
```

### 🚫 Use Models Without Prompts

```bash
curl -X POST http://127.0.0.1:3781/v1/easyearth/predict \
-H "Content-Type: application/json" \
-d '{
  "model_type": "segment",
  "image_path": "/usr/src/app/data//DJI_0108.JPG",
  "model_path": "restor/tcd-segformer-mit-b2",
  "prompts": []
}'
```

## Swagger UI
You can also access the Swagger UI to test the APIs:
```bash
http://localhost:3781/v1/easyearth/ui
```


## 🔌 Run EasyEarth Outside QGIS

You can also run EasyEarth server headlessly:

1. Start the Docker container
```bash
cd easyearth_plugin  # go to the directory where the repo is located
sudo TEMP_DIR=/custom/temp/data DATA_DIR=/custom/data/path LOG_DIR=/custom/log/path MODEL_DIR=/custom/cache/path docker-compose up -d # start the container while mounting the custom directories.
```
2. Use Rest API to send requests to the server, check [Model APIs](#-model-apis) for more details.


### ✅ Health Check
Check if the server is running, the response should be `Server is alive`

```bash
curl -X GET http://127.0.0.1:3781/v1/easyearth/ping
```

---

## Create local environment for running EasyEarth without Docker
To create a local environment for development, you can use the following steps:
```bash
cd easyearth  # go to the directory where requirements.txt is located
python -m venv --copies easyearth_env  # Create a virtual environment, remember to use `--copies` to avoid issues with symlinks
source easyearth_env/bin/activate  # Activate the virtual environment
pip install -r requirements.txt  # Install the required packages
```