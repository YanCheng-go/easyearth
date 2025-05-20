#!/bin/bash

# Exit on any error
set -e

# Set the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="easyearth_plugin_easyearth-server"
MODEL_DIR="~/.cache/easyearth/models"

# Change the permissions of the script directory
sudo chmod -R 755 "$SCRIPT_DIR"

# Function to ensure Docker Compose is installed
check_docker_installation() {
  if ! command -v docker-compose &>/dev/null; then
    echo "Installing docker-compose..."
    sudo apt-get update && sudo apt-get install -y docker-compose
  else
    echo "docker-compose is already installed."
  fi
}

# if not cache folder exists, create it
create_cache_folder() {
  if [ ! -d "$MODEL_DIR" ]; then
    mkdir -p "$MODEL_DIR"
    chmod -R 755 "$MODEL_DIR"
  fi
}

# Check if the docker image easyearth_plugin_easyearth-server exists, if exists return 0 else return 1
check_docker_image() {
  if sudo docker images | grep -q "$IMAGE_NAME"; then  # TODO: for some reason docker-compose images is not working... if using docker... need to make sure docker is installed...
    echo "Docker image $IMAGE_NAME already exists."
    return 0
  else
    echo "Docker image $IMAGE_NAME does not exist."
    return 1
  fi
}

# Function to configure directories
configure_directory() {
  local dir_name="$1"
  local default_dir="$2"
  local result_dir

  read -p "Specify folder for $dir_name (default: $default_dir): " result_dir
  result_dir="${result_dir:-$default_dir}"

  [ ! -d "$result_dir" ] && mkdir -p "$result_dir" && echo "Created $dir_name at $result_dir"
  chmod -R 755 "$result_dir"
  echo "$result_dir"
}

# Build Docker image
build_docker_image() {
  echo "Building Docker image..."
  sudo docker-compose build --no-cache
}

# Start Docker container
start_docker_container() {

  # Configure directories
  DATA_DIR=$(configure_directory "data directory" "./data")
  TEMP_DIR=$(configure_directory "temp directory" "./tmp")
  MODEL_DIR=$(configure_directory "model cache directory" "$MODEL_DIR")
  LOG_DIR=$(configure_directory "logs directory" "./logs")

  # check if there is one running container
  if sudo docker-compose ps -q --filter "name=$IMAGE_NAME" | grep -q .; then
    echo "Stopping existing Docker container..."
    sudo docker-compose down
  fi
  echo "Starting Docker container..."
  sudo TEMP_DIR="$TEMP_DIR" DATA_DIR="$DATA_DIR" LOG_DIR="$LOG_DIR" MODEL_DIR="$MODEL_DIR" docker-compose up -d
}

# Test if the server is running
test_server() {
  echo "Testing if the server is running..."
  sleep 5
  if curl -s http://localhost:3781/v1/easyearth/ping | grep -q "Server is alive"; then
    echo "Server is running!"
  else
    echo "Server is not running. Check the logs."
    exit 1
  fi
}

# Main execution
main() {
  echo "Starting setup..."
  check_docker_installation

  if check_docker_image; then
    echo "Skipping Docker image build."
  else
    build_docker_image
  fi

  create_cache_folder

  start_docker_container
  test_server

  echo "Setup completed successfully!"
}

# Run the script
main
