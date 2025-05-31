# EasyEarth: Run Vision(-Language) Models for Earth Observations at Your Fingertips

<p align="center">
  <img src="./easyearth_plugin/resources/icons/easyearth.png" alt="EasyEarth Logo" width="200"/>
</p>

<p align="center">
  <a href="https://github.com/YanCheng-go/easyearth/actions/workflows/deploy.yml">
    <img src="https://github.com/YanCheng-go/easyearth/actions/workflows/deploy.yml/badge.svg" alt="CI Status"/>
  </a>
  <a href="https://github.com/YanCheng-go/easyearth/releases">
    <img src="https://img.shields.io/github/v/release/YanCheng-go/easyearth?label=Release&logo=github" alt="GitHub Release"/>
  </a>
  <a href="https://github.com/YanCheng-go/easyearth/issues">
    <img src="https://img.shields.io/github/issues/YanCheng-go/easyearth?logo=github" alt="GitHub Issues"/>
  </a>
  <a href="https://github.com/YanCheng-go/easyearth/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/YanCheng-go/easyearth?label=License&logo=github" alt="License"/>
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/OS-Ubuntu-blue?logo=ubuntu" alt="Ubuntu"/>
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/OS-macOS-lightgrey?logo=apple" alt="macOS"/>
  </a>

[//]: # (  <a href="#">)

[//]: # (    <img src="https://img.shields.io/badge/OS-Windows-blue?logo=windows" alt="Windows"/>)

[//]: # (  </a>)
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
- [Usage](#-usage)
  - [Run EasyEarth in QGIS](#-run-easyearth-in-qgis)
  - [Run EasyEarth Outside QGIS](#-run-easyearth-outside-qgis)
  - [Health Check](#-health-check)
- [Documentation](#-documentation)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [Authors](#-authors)

## 📁 Project Structure

```bash
.
├── easyearth  # Server-side code for EasyEarth
│   ├── app.py  # Main application entry point
│   ├── config  
│   ├── controllers  # Controllers for handling requests
│   ├── models  # Model management and inference logic
│   ├── openapi  # OpenAPI specification for the API
│   ├── static  # Static files for the server
│   ├── tests  # Unit tests for the server
├── easyearth_plugin  # QGIS plugin for EasyEarth
│   ├── core  # Core logic for the plugin
│   ├── data  # Sample data for testing
│   ├── environment.yml  
│   ├── launch_server_local.sh  # Script to launch server locally
│   ├── plugin.py  # Main plugin entry point
│   ├── requirements.txt  # Python dependencies for the plugin
│   ├── resources  # Resources for the plugin (icons, images, etc.)
│   └── ui  # User interface files for the plugin
├── docs  # Documentation for EasyEarth
│   ├── APIReference.md  # API reference documentation
│   └── DeveloperGuide.md  # Developer guide for contributing to EasyEarth
├── docker-compose.yml  # Docker Compose configuration for EasyEarth
├── Dockerfile  # Dockerfile for building the EasyEarth server image
├── environment.yml  # Conda environment file for EasyEarth
├── launch_server_local.sh  # Script to launch the EasyEarth server locally
├── README.md  
├── requirements_mac.txt  # Python dependencies for macOS
├── requirements.txt  # Python dependencies for EasyEarth
├── setup.sh  # Script to set up the dockerized EasyEarth server (only needed for building the image from the start)

    
```

---
## Get Started

### ✅ Requirements

- Docker Compose ≥ 1.21.2 ([install guide](https://docs.docker.com/compose/install/))
- Python ≥ 3.6
- CUDA ≥ 12.4 ([download](https://developer.nvidia.com/cuda-downloads))  
 _⚠️ CUDA is **only required** for GPU inference. CPU-only mode is also available (though slower)_
- (optional) [QGIS](https://qgis.org) > = 3.22 (tested with 3.38 and 3.40)
 _⚠️ to use the plugin on QGIS, otherwise, one can use the server side only_

### 📦 Compatibility
Currently tested on:<br>
✅ Ubuntu<br>
✅ macOS<br>
⚠️ Windows support:<br>
We have not yet tested EasyEarth on Windows. If you encounter any issues or would like to help us add Windows support, contributions are welcome!

### 📥 Download Pre-built Plugin

```bash
# go to your download directory
cd ~/Downloads  # Specify your own path where you want to download the code
git clone https://github.com/YanCheng-go/easyearth.git
```

You can also download the latest release (.zip) directly from the [Releases Page](https://github.com/YanCheng-go/easyearth/releases).


### 🧩 Install EasyEarth Plugin in QGIS

#### Method 1: Manual Installation
1. Open QGIS > `Settings` > `User Profiles` > `Open Active Profile Folder`
2. Navigate to `python/plugins`
3. Copy `easyearth_plugin` folder into this directory
4. Restart QGIS > `Plugins` > `Manage and Install Plugins` > enable **EasyEarth**

#### Method 2: Terminal Installation

```bash
cd ~/Downloads/easyearth/easyearth_plugin  # go to the directory where easyearth_plugin is located
cp -r ./easyearth_plugin ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins  # copy the easyearth_plugin folder to the plugins directory
```
After this, Restart QGIS > `Plugins` > `Manage and Install Plugins` > enable **EasyEarth**

---
## 🚀 Usage

### 🛰️ Run EasyEarth in QGIS
1. Click on the **EasyEarth** icon in the toolbar
2. Select a project directory, some folders will be created in the project directory, the structure is as follows:
   - `easyearth_base/images`<br>_⚠️images to be processed need to be placed here_
   - `easyearth_base/embeddings` - for storing embeddings
   - `easyearth_base/logs` - for storing logs
   - `easyearth_base/tmp` - for storing temporary files
   - `easyearth_base/predictions ` - for storing predictions
3. Click **Docker** to launch the EasyEarth server dockerized container, or **Local** to run the non-dockerized server
4. Then you will see the Server Status as **Online - Device: <DEVICE INFO>** in the Server section
5. Click **Browse Image** to select an image from the `easyearth_base/images` folder
6. Select a model from the dropdown menu
7. Click **Start Drawing** to draw points or boxes on the image <br>_⚠️when the real time mode is checked, the prediction of each drawing prompt will be shown in real time, so no need to go step 8_
8. Click **Predict** to run the model inference
9. Prediction results will be saved in the easyearth_base/tmp folder and can be moved to the easyearth_base/predictions folder as desired.
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

## 📚 Documentation
Check out our User Guide and Developer Guide for more.
- [Developer Guide](docs/DeveloperGuide.md)  # for developers to contribute and extend EasyEarth
- [API Reference](docs/APIReference.md)  # for developers to use the EasyEarth APIs
---

## ✅ Roadmap
- [x] EasyEarth server for model inference
- [x] QGIS plugin for model application
- [x] Dockerized server for scalable model inference
- [x] Advanced prompt-guided segmentation
- [ ] Editing tools for segmentation
- [ ] Model Manager for uploading/updating/tracking models
- [ ] Chatbot integration for model management and reporting
- [ ] Cloud deployment templates

---

## 🤝 Contributing

We welcome community contributions! If you'd like to contribute, check out:
- [`CONTRIBUTING.md`](CONTRIBUTING.md)
---

## 🧑‍💻 Authors

Developed by: <br>
**Yan Cheng** ([chengyan2017@gmail.com](mailto:chengyan2017@gmail.com)) – 
[🌐 Website](https://yancheng-website.com)
<a href="https://github.com/YanCheng-go" style="margin-left: 0.5em;">
  <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/github.svg" alt="GitHub" width="20" style="vertical-align: middle;"/> GitHub
</a>
<a href="https://www.linkedin.com/in/yancheng" style="margin-left: 0.5em;">
  <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/linkedin.svg" alt="LinkedIn" width="20" style="vertical-align: middle;"/> LinkedIn
</a><br>
**Ankit Kariryaa** ([ankit.ky@gmail.com](mailto:ankit.ky@gmail.com)) – <br> 
**Lucia Gordon** ([luciagordon@g.harvard.edu](mailto:luciagordon@g.harvard.edu)) – 

---
