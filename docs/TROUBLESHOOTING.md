# Troubleshooting Guide

## Issues with Docker (Linux Only)

If you encounter issues with Docker during setup or usage, ensure that Docker is properly installed and configured on your system. For Linux Ubuntu users, refer to our [Docker Installation Guide](docs/docker_installation_for_ubuntu.md) for step-by-step instructions.

### Common Docker Issues:
1. **Docker Command Not Found**:
   - Ensure Docker is installed. Run `docker --version` to verify.
   - If not installed, follow the [Docker Installation Guide](docs/docker_installation_for_ubuntu.md).

2. **Permission Denied Errors**:
   - Add your user to the `docker` group:  
     ```bash
     sudo usermod -aG docker $USER
     newgrp docker
     docker run hello-world
     ```   
  - if the last command line here is not giving any error, meaning you have set the permission correctly
  - Reboot to activate the effect
  - Check this for more information: https://docs.docker.com/engine/install/linux-postinstall/
   

3. **Cannot Connect to Docker Daemon**:
   - Ensure the Docker service is running:
     ```bash
     sudo systemctl start docker
     sudo systemctl enable docker
     ```

4. **Auto-detected mode as 'legacy'\nnvidia-container-cli: initialization error: nvml error: driver/library version mismatch: unknown**:

   This error means that there is a mismatch between the driver and the kernel, which sometimes happens with automatic system updates. Restart or reboot to solve this issue.
   

## Install local environment instead
If you prefer to run the EasyEarth server without Docker, you can set up a local Python environment.

### macOS / Linux
```bash
cd easyearth_base # Create a work directory
cp <PROJECT FOLDER>/easyearth/requirements.txt .  # Copy the requirements file to the current directory
python -m venv --copies easyearth_env  # Create a virtual environment, remember to use `--copies` to avoid issues with symlinks
source easyearth_env/bin/activate  # Activate the virtual environment
pip install -r requirements.txt  # Install the required packages
```

### Windows
```cmd
cd easyearth_base
copy <PROJECT FOLDER>\easyearth\requirements.txt .
python -m venv --copies easyearth_env
easyearth_env\Scripts\activate
pip install -r requirements.txt
```

### Windows-specific notes
- Docker Desktop must be installed and running for Docker mode. The plugin looks for Docker at `C:\Program Files\Docker\Docker\resources\bin\docker.exe` if `docker` is not on the system PATH.
- For local mode, use the `launch_server_local.bat` script or run `python -m easyearth.app` directly.
- Set the `BASE_DIR` environment variable to your working directory before starting the server. If not set, it defaults to `%USERPROFILE%\.easyearth`.
