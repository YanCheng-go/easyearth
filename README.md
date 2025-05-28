# EasyEarth: Run Vision(-Language) Models for Earth Observations at Your Fingertips

<p align="center">
  <img src="./easyearth_plugin/resources/icons/easyearth.png" alt="EasyEarth Logo" width="200"/>
</p>

EasyEarth enables seamless application of cutting-edge computer vision and vision-language models directly on Earth observation data — without writing code. The platform integrates with [QGIS](https://qgis.org) via a plugin GUI and provides server-side infrastructure for scalable model inference and management.

---

## 🔧 Key Components

1. **Server-Side Infrastructure** – Scalable backend to run AI models on geospatial data
2. **QGIS Plugin GUI** – User-friendly interface to apply models inside QGIS
3. **Model Manager** *(in development)* – Upload, version, and deploy models with ease

![Architecture](https://github.com/user-attachments/assets/91f2cad0-4cbb-4b9b-a7e4-2cd2d247cc42)


📽️ **[Watch Demo](https://drive.google.com/file/d/1AShHsXkYoBj4zltAGkdnzEfKp2GSFFeS/view)**

---

## Table of Contents
- [Project Structure](#-project-structure)
- [Get Started](#-get-started)
  - [Requirements](#-requirements)
  - [Clone Repository](#-clone-repository)
  - [Set Up Docker Server](#-set-up-docker-server)
    - [Stop the Server](#-stop-the-server)
    - [Useful Docker Commands](#-useful-docker-commands)
  - [Install EasyEarth Plugin in QGIS](#-install-easyearth-plugin-in-qgis)
    - [Method 1: Manual Installation](#method-1-manual-installation)
    - [Method 2: Terminal Installation](#method-2-terminal-installation)
- [Available Models](#-available-models-adding)
- [Model APIs](#-model-apis)
  - [Use SAM with Prompts](#-use-sam-with-prompts)
  - [Use Models Without Prompts](#-use-models-without-prompts)
- [Usage](#-usage)
  - [Run EasyEarth in QGIS](#-run-easyearth-in-qgis)
  - [Run EasyEarth Outside QGIS](#-run-easyearth-outside-qgis)
  - [Health Check](#-health-check)
- [Documentation](#-documentation)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [Author](#-author)
- [License](#-license)

## 📁 Project Structure

```bash
easyearth/
├── easyearth/         # Server app – use this if you're only interested in the backend
├── easyearth_plugin/  # QGIS plugin – use this folder to install the QGIS interface
    ├── core/               # Core plugin files
    ├── resources/          # Plugin resources (icons, images, etc.)
    ├── ui/                 # Plugin UI files
├── Dockerfile             # Dockerfile to build the EasyEarth server image
├── docker-compose.yml # Docker Compose file to set up the server
├── launch_server_local.sh # Script to run the server locally
├── setup.sh           # Script to set up the Docker server
├── requirements.txt   # Python dependencies for the server
├── README.md          # Project documentation
└── docs/              # Documentation files
    ├── DeveloperGuide.md
    
```

---
## Get Started

### ✅ Requirements

- Docker Compose ≥ 1.21.2 ([install guide](https://docs.docker.com/compose/install/))
- Python ≥ 3.6
- [QGIS](https://qgis.org)
- CUDA ≥ 12.4 ([download](https://developer.nvidia.com/cuda-downloads))  
  _⚠️ More info on CUDA compatibility coming soon_

### 📥 Clone Repository

```bash
# go to your download directory
cd ~/Downloads  # Specify your own path where you want to download the code
git clone https://github.com/YanCheng-go/easyearth.git
cp -r ./easyearth/easyearth_plugin easyearth_plugin
```

### Local mode
Run in a terminal
```bash
chmod +x ./launch_server_local.sh && ./launch_server_local.sh
```

### 🐳 Set Up Docker Server

This will install Docker, build the image, and launch the EasyEarth server.

```bash
cd easyearth_plugin  # go to the directory where docker-compose.yml is located
chmod +x ./setup.sh  # make the setup.sh executable
./setup.sh  # run the setup.sh script
```

#### 🛑 Stop the Server

```bash
cd easyearth_plugin  # go to the directory where docker-compose.yml is located
sudo docker-compose down  # stop the docker container
```

#### 🛠 Useful Docker Commands

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

```

### 🧩 Install EasyEarth Plugin in QGIS

#### Method 1: Manual Installation
1. Open QGIS > `Settings` > `User Profiles` > `Open Active Profile Folder`
2. Navigate to `python/plugins`
3. Copy `easyearth_plugin` folder into this directory
4. Restart QGIS > `Plugins` > `Manage and Install Plugins` > enable **EasyEarth**

#### Method 2: Terminal Installation

```bash
cd ~/Downloads/easyearth_plugin  # go to the directory where easyearth_plugin is located
cp -r ./easyearth_plugin ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins  # copy the easyearth_plugin folder to the plugins directory
```

---
## 🚀 Usage

### 🛰️ Run EasyEarth in QGIS

1. Stop external Docker containers:
   ```bash
    cd easyearth_plugin  # go to the directory where docker-compose.yml is located
    sudo docker-compose down  # stop the docker container
   ```
2. Open QGIS, click **Start Docker**
3. Load an image using **Browse Image**
4. Click **Start Drawing**

![QGIS Plugin GUI](https://github.com/user-attachments/assets/7233c11c-cc7f-4fd8-8dc5-196db4a4220b)

---
## 🧠 Available Models (Adding...)
| Model Name                  | Description | Prompt Type | Prompt Data           |
|-----------------------------|-------------|----------|-----------------------|
| SAM                         | Segment Anything Model | Point    | [[x, y], [x, y], ...] |
| SAM                         | Segment Anything Model | Box      | [[x1, y1, x2, y2]]    |
| SAM2                        | Segment Anything Model | Point    | [[x, y], [x, y], ...] |
| SAM2                        | Segment Anything Model | Box      | [[x1, y1, x2, y2]]    |
| LangSAM                     | Language Model | Text     | ["text1", "text2"]    |
| restor/tcd-segformer-mit-b2 | Semantic Segmentation | None     | []                    |


---

## 📚 Documentation (TO BE UPDATED)
Check out our User Guide and Developer Guide for more.
- [User Guide](docs/UserGuide.md)
- [Developer Guide](docs/DeveloperGuide.md)
- [API Reference](docs/APIReference.md)
- [Model Management](docs/ModelManagement.md)
- [QGIS Plugin](docs/QGISPlugin.md)
- [Docker Setup](docs/DockerSetup.md)

---

## ✅ Roadmap

- [x] EasyEarth server for model inference
- [x] QGIS plugin for model application
- [x] Dockerized server for scalable model inference
- [x] Advanced prompt-guided segmentation
- [ ] Compelet documentation
- [ ] Editing tools for segmentation
- [ ] Model Manager for uploading/updating/tracking models
- [ ] Chatbot integration for model management and reporting
- [ ] Cloud deployment templates


---

## 🤝 Contributing

We welcome community contributions! If you'd like to contribute, check out:
- [`CONTRIBUTING.md`](CONTRIBUTING.md)

[//]: # (- [`docs/DeveloperGuide.md`]&#40;docs/DeveloperGuide.md&#41;)

---

## 🧑‍💻 Author

Developed by: **Yan Cheng (chengyan2017@gmail.com), Ankit Kariryaa (ankit.ky@gmail.com), Lucia Gordon (luciagordon@g.harvard.edu)**

[//]: # (🌐 [Website] • [GitHub] • [LinkedIn])

---
