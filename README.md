# Easy Earth project with Flask, Connexion and OpenApi 3


EasyEarth - QGIS plugin powered by huggingface, Flask and Connexion 

Check the demo [here](https://drive.google.com/file/d/1AShHsXkYoBj4zltAGkdnzEfKp2GSFFeS/view)


![image](https://github.com/user-attachments/assets/749cc195-a149-4ccd-9d3f-edb3a2040cf7)


```http
https://github.com/zalando/connexion
```

## Folder structure
```
easyearth
├── easyearth  -> server app use this as the project folder if you are only interested in the server side not the qgis plugin
├── easyearth_plugin  -> qgis plugin use this as the project folder if you are using qgis plugin
│   ├── easyearth  -> server app the same file as in easyearth
│   ├── ...
```

## Requirements

* Docker Compose 1.21.2+ (see https://docs.docker.com/compose/install/)
* Python 3.6 +
* QGIS (Download from https://www.qgis.org/)
* CUDA 12.4 + (Download from https://developer.nvidia.com/cuda-downloads)  # TODO: more information on cuda compatibility, add the blog about compatibility

## Download the project repository
```bash
# go to your download directory
cd ~/Downloads  # Specify your own path where you want to download the code
git clone https://github.com/YanCheng-go/easyearth.git
cp -r ./easyearth/easyearth_plugin easyearth_plugin
```

## Set up the docker container
This step will install docker-compose, build the docker image, and start the container with the server running.
```bash
cd easyearth_plugin  # go to the directory where docker-compose.yml is located
chmod +x ./setup.sh  # make the setup.sh executable
./setup.sh  # run the setup.sh script
```

## Stop the docker container
```bash
cd easyearth_plugin  # go to the directory where docker-compose.yml is located
sudo docker-compose down  # stop the docker container
```

## Install easyearth plugin on qgis
1. Open QGIS, click Settings -> User profiles -> Open Active Profile Folder -> python -> plugins
2. Copy easyearth_plugin folder to "plugins"
3. Reopen QGIS, click Plugins -> Manage and Install Plugins -> Installed -> click the check box before EasyEarth

or in terminal:
```bash
cd ~/Downloads/easyearth_plugin  # go to the directory where easyearth_plugin is located
cp -r ./easyearth_plugin ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/  # copy the easyearth_plugin folder to the plugins directory
```

## Run EasyEarth in QGIS
1. Stop the docker container if it is running outside of QGIS. Open a terminal and run:
    ```bash
    cd easyearth_plugin  # go to the directory where docker-compose.yml is located
    sudo docker-compose down  # stop the docker container
    ```
2. In QGIS, click Start Docker
3. Click Browse image and select an image to play with 
4. Click Start Drawing.

## Run EasyEarth outside QGIS
Start the docker container and send requests to the server using curl or any other HTTP client.
```bash
cd easyearth_plugin  # go to the directory where the repo is located
sudo TEMP_DIR=/custom/temp/data DATA_DIR=/custom/data/path LOG_DIR=/custom/log/path MODEL_DIR=/custom/cache/path docker-compose up -d # start the container while mounting the custom directories.
```

### Health Check
Check if the server is running, the response should be `Server is alive`
```bash
curl -X GET http://127.0.0.1:3781/v1/easyearth/ping'
```
### Use SAM with prompts
Send prompts to the server and get predictions from SAM model. Check the generated geojson in easyearth_plugin/user/tmp/...
```bash
curl -X POST http://127.0.0.1:3781/v1/easyearth/sam-predict -H "Content-Type: application/json" -d '{
  "image_path": "/usr/src/app/user/DJI_0108.JPG",
  "embedding_path": "/usr/src/app/user/embeddings/DJI_0108.pt",  # if empty, the code will generate embeddings first
  "prompts": [
    {
      "type": "Point",
      "data": {
        "points": [[850, 1100]],
      }
    }  
                      
  ]            
}'
```
### Use models with no prompts
Call other segmentation models with out prompt engineering
```bash
curl -X POST http://127.0.0.1:3781/v1/easyearth/segment-predict -H "Content-Type: application/json" -d '{
  "image_path": "/usr/src/app/user/DJI_0108.JPG",
  "prompts": []
}'
```

### Swagger definition
```http
http://localhost:3781/v1/easyearth/swagger.json  # TODO: not working yet...
```

## Launch tests  # TODO: to add

```bash
source venv/bin/activate
tox
```

## Useful docker commands
```bash
# List all docker containers
docker ps -a
# List all docker images
docker images
# Remove all docker containers
docker rm $(docker ps -a -q)
# Remove all docker images
docker rmi $(docker images -q)
# Remove all docker volumes
docker volume rm $(docker volume ls -q)
# check the logs of the container, where you can also get information on the mounted directories
sudo docker inspect <container_id>
# check the mounted directory in a running docker container
sudo docker exec -it <container_id_or_name> /usr/src/app
```
