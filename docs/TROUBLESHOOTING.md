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
