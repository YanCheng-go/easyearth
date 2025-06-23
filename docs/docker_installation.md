# Docker Setup on Linux

This guide explains how to install Docker on a Linux system running Ubuntu.

---

## Prerequisites
Ensure your system is up-to-date:
```bash
sudo apt update
sudo apt upgrade -y
```

---

## Installation Steps

### 1. Remove Existing Docker Installation (Snap Version)
If Docker is installed using Snap, remove it:
```bash
sudo snap remove docker
```

### 2. Install Dependencies
Install required packages for adding repositories securely:
```bash
sudo apt install apt-transport-https ca-certificates curl software-properties-common
```

### 3. Add Docker’s Official GPG Key
Download and save Docker’s GPG key:
```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
```

### 4. Add Docker’s Repository
Add the Docker stable repository to your sources list:
```bash
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### 5. Update Package List
Update your system's package list to include Docker packages:
```bash
sudo apt update
```

### 6. Install Docker
Install Docker Community Edition:
```bash
sudo apt install docker-ce -y
```

### 7. Verify Installation
Check Docker's version:
```bash
docker --version
```
Run a test container:
```bash
docker run hello-world
```

---

## Post-Installation Steps
To avoid using `sudo` with Docker commands, add your user to the Docker group:
```bash
sudo usermod -aG docker $USER
```

**Important:** Log out and log back in for the changes to take effect. Alternatively, use:
```bash
newgrp docker
```

---

## Troubleshooting
If you encounter issues, refer to the official Docker documentation: [https://docs.docker.com/engine/install/ubuntu/](https://docs.docker.com/engine/install/ubuntu/)

---
