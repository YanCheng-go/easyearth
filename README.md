# EasyEarth: Run Vision(-Language) Models for Earth Observations at Your Fingertips

<p align="center">
  <img src="./easyearth_plugin/resources/icons/easyearth.png" alt="EasyEarth Logo" width="200"/>
</p>

<p align="center">
  <a href="https://github.com/YanCheng-go/easyearth/actions/workflows/deploy.yml">
    <img src="https://github.com/YanCheng-go/easyearth/actions/workflows/deploy.yml/badge.svg" alt="Deploy Dokcer"/>
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
  <a href="#">
    <img src="https://img.shields.io/badge/OS-Windows-blue?logo=windows" alt="Windows"/>
  </a>
  <a href="https://doi.org/10.5281/zenodo.15699316">
    <img src="https://zenodo.org/badge/DOI/10.5281/zenodo.15699316.svg" alt="DOI"/>
  </a>
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
- [Compatibility](#-compatibility)
- [Get Started](#-get-started)
  - [Requirements](#-requirements)
  - [Clone Repository](#-download-pre-built-plugin)
  - [Install EasyEarth Plugin in QGIS](#-install-easyearth-plugin-in-qgis)
    - [Method 1: Manual Installation](#method-1-manual-installation)
    - [Method 2: Terminal Installation](#method-2-terminal-installation)
- [Available Models](#-available-models-adding)
- [Usage](#-usage)
- [Documentation](#-documentation)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [Acknowledgements](#-acknowledgements)
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
## 🚀 Get Started

### ✅ Requirements


- Python ≥ 3.9
- (optional) [QGIS](https://qgis.org) (tested with 3.38 and 3.40) <br>_⚠️ required to use the plugin on QGIS, otherwise, one can use the server side only_
- (optional) CUDA ≥ 12.4 ([download](https://developer.nvidia.com/cuda-downloads)) <br>_⚠️ CUDA is **only required** for GPU inference on Linux. CPU-only mode is also available (though much slower)_
- (optional) Docker and Docker Compose ≥ 1.21.2 ([install guide](https://docs.docker.com/get-started/get-docker/)) <br>_⚠️ The server side is a dockerized Flask APP. Without Docker, one can use the local server mode in the plugin, which will download and use a pre-compressed env file for running the app without Docker_
- (optional) NVIDIA Container Toolkit ([install guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html))<br>_⚠️ To use GPU with docker container, only required if you want to use the docker mode_
### 📦 Compatibility
Currently tested on:<br>
✅ Ubuntu<br>
✅ MacOS<br>
⚠️ Windows support:<br>
Please find the pre-release for Windoes [here](https://github.com/YanCheng-go/easyearth/releases/tag/v0.0.3.dev). We haven't finished the full test for Windows - if you encounter any issues or would like to help us add Windows support, contributions are welcome!

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
cp -r ./easyearth_plugin ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins  # copy the easyearth_plugin folder to the plugins directory on Linux
cp -r easyearth_plugin /Users/USERNAME/Library/Application\ Support/QGIS/QGIS3/profiles/default/python/plugins # copy the easyearth_plugin folder to the plugins directory on Mac
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
3. Click **Docker** to launch the EasyEarth server dockerized container, or **Local** to run the non-dockerized server <br>_⚠️ This may take a while the first time and when there is an updated docker image. As a faster option, one can pull the docker image outside QGIS using the terminal and run "docker pull maverickmiaow/easyearth:latest"_
4. Then you will see the Server Status as **Online - Device: <DEVICE INFO>** in the Server section
5. Click **Browse Image** to select an image from the `easyearth_base/images` folder
6. Select a model from the dropdown menu
7. Click **Start Drawing** to draw points or boxes on the image <br>_⚠️when the real-time mode is checked, the prediction of each drawing prompt will be shown in real time, so no need to go step 8_
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

## 🎯 Roadmap
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

## 👥 Acknowledgements

This project was inspired by several outstanding open-source initiatives. We extend our gratitude to the developers and communities behind the following projects:

- **[Segment Anything (SAM)](https://github.com/facebookresearch/segment-anything)** – Meta AI's foundation model for promptable image and video segmentation.
- **[SAMGeo](https://github.com/opengeos/segment-geospatial)** – A Python package for applying SAM to geospatial data.
- **[Geo-SAM](https://github.com/coolzhao/Geo-SAM)** – A QGIS plugin for efficient segmentation of large geospatial raster images.
- **[GroundingDINO](https://github.com/IDEA-Research/GroundingDINO)** – An open-set object detector integrating language and vision for zero-shot detection.
- **[Lang-Segment-Anything](https://github.com/luca-medeiros/lang-segment-anything)** – Combines SAM and GroundingDINO to enable segmentation via natural language prompts.
- **[Ultralytics](https://github.com/ultralytics/ultralytics)** – Creators of the YOLO series, offering real-time object detection and segmentation models.
- **[Hugging Face](https://huggingface.co)** – A platform for sharing and collaborating on machine learning models and datasets.
- **[Ollama](https://ollama.com)** – A framework for running large language models locally with ease.

## 🧑‍💻 Authors

Developed by:

Yan Cheng ([chengyan2017@gmail.com](mailto:chengyan2017@gmail.com)) – 
[🌐 Website](https://yancheng-website.com)
<a href="https://github.com/YanCheng-go" style="margin-left: 0.5em;">
  <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/github.svg" alt="GitHub" width="20" style="vertical-align: middle;"/> GitHub
</a>
<a href="https://www.linkedin.com/in/yancheng" style="margin-left: 0.5em;">
  <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/linkedin.svg" alt="LinkedIn" width="20" style="vertical-align: middle;"/> LinkedIn
</a><br>
Lucia Gordon ([luciagordon@g.harvard.edu](mailto:luciagordon@g.harvard.edu)) – 
[🌐 Website](https://lgordon99.github.io)
<a href="https://github.com/lgordon99" style="margin-left: 0.5em;">
  <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/github.svg" alt="GitHub" width="20" style="vertical-align: middle;"/> GitHub
</a>
<a href="http://www.linkedin.com/in/lucia-gordon-187069225" style="margin-left: 0.5em;">
  <img src="https://cdn.jsdelivr.net/gh/simple-icons/simple-icons/icons/linkedin.svg" alt="LinkedIn" width="20" style="vertical-align: middle;"/> LinkedIn
</a><br>
Ankit Kariryaa ([ankit.ky@gmail.com](mailto:ankit.ky@gmail.com))

## Citation
If you use EasyEarth in your research or projects, please cite it as follows:

```bibtex
@software{easyearth2025,
  author = {Yan Cheng and Lucia Gordon and Ankit Kariryaa},
  title = {EasyEarth: Run Vision(-Language) Models for Earth Observations at Your Fingertips},
  year = {2025},
  publisher = {GitHub},
  journal = {GitHub repository},
  url = {https://github.com/YanCheng-go/easyearth},
  doi = {10.5281/zenodo.15699316},
}
```

---