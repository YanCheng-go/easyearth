EasyEarth Developer Guide
=========================
This guide provides instructions for developers to set up and run the EasyEarth server outside of QGIS, including how to use the model APIs.

## 🐳 Set Up Docker Server
This will install Docker, build the image, and launch the EasyEarth server.
If you make changes to the code, you can rebuild the Docker image using:
```bash
cd easyearth  # go to the directory where docker-compose.yml is located
./setup.sh  # run the setup.sh script to rebuild the Docker image, remember to setup the data folder.
```
stop the server first if it is running:
```bash
cd easyearth  # go to the directory where docker-compose.yml is located
sudo docker-compose down  # stop the docker container
```

## Run local server without Docker
1. Create a local python environment:
```bash
cd easyearth  # go to the directory where requirements.txt is located
python -m venv --copies easyearth_env  # Create a virtual environment, remember to use `--copies` to avoid issues with symlinks
source easyearth_env/bin/activate  # Activate the virtual environment
pip install -r requirements.txt  # Install the required packages
```
2. Launch the server, this bash also checks if the python environment exists and activates it:
```bash
cd easyearth  # go to the directory where requirements.txt is located
chmod +x ./launch_server_local.sh && ./launch_server_local.sh
```

## 🧪 Test the Server and model APIs
### 📍 Use SAM with Prompts

```bash
curl -X POST http://127.0.0.1:3781/easyearth/predict \
-H "Content-Type: application/json" \
-d '{
  "model_type": "sam",
  "image_path": "/usr/src/app/data/DJI_0108.JPG",
  "embedding_path": "/usr/src/app/data/embeddings/DJI_0108.pt",
  "model_path": "facebook/sam-vit-base",
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
curl -X POST http://127.0.0.1:3781/easyearth/predict \
-H "Content-Type: application/json" \
-d '{
  "model_type": "segment",
  "image_path": "/usr/src/app/data/DJI_0108.JPG",
  "model_path": "restor/tcd-segformer-mit-b2",
  "prompts": [],
  "aoi": (0, 0, 1000, 1000)
}'
```

## Swagger UI
You can also access the Swagger UI to test the APIs:
```bash
http://localhost:3781/easyearth/ui
```

---

## 🛠 Useful Docker Commands

```bash

# List containers
docker ps -a
# List images
docker images
# Remove all containers
docker rm $(docker ps -a -q)
# Remove all images
docker rmi $(docker images -q)
# Remove all volumes
docker volume rm $(docker volume ls -q)
# Inspect container
sudo docker inspect <container_id>
# Access container shell
sudo docker exec -it <container_id_or_name> /usr/src/app
# Run in an interactive mode
sudo docker run -it --entrypoint /bin/bash --rm -v /path/to/your/easyearth_base:/usr/src/app/data maverickmiaow/easyearth:latest

```