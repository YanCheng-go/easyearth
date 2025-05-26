#!/bin/bash

# Exit on any error
set -e

# Set the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="easyearth_easyearth-server"
MODEL_DIR="~/.cache/easyearth/models"

apt_get_command() {
  local command=("${@}")

  if ! apt-get "${command[@]}"; then
    brew "${command[@]}"
  fi
}

execute_command_with_sudo() {
  echo "Executing with sudo"
  local command=("${@}")
  "${command[@]}"
}

execute_command() {
  local command=("${@}")

  if ! "${command[@]}"; then
    execute_command_with_sudo sudo "${command[@]}"
  fi
}

# Change the permissions of the script directory
execute_command chmod -R 755 "$SCRIPT_DIR"

# Function to ensure Docker Compose is installed
check_docker_installation() {
  if ! command -v docker-compose &>/dev/null; then
    echo "Installing docker-compose..."
    execute_command apt_get_command update
    execute_command apt_get_command install -y docker-compose
  else
    echo "docker-compose is already installed."
  fi
}

# Check if the docker image easyearth_plugin_easyearth-server exists, if exists return 0 else return 1
check_docker_image() {
  if execute_command docker images | grep -q "$IMAGE_NAME"; then  # TODO: for some reason docker-compose images is not working... if using docker... need to make sure docker is installed...
    echo "Docker image $IMAGE_NAME already exists."
    return 0
  else
    echo "Docker image $IMAGE_NAME does not exist."
    return 1
  fi
}

build_docker_image() {
  echo "Building Docker image..."
  execute_command docker-compose build --no-cache
}

# if not cache folder exists, create it
create_cache_folder() {
  if [ ! -d "$MODEL_DIR" ]; then
    mkdir -p "$MODEL_DIR"
    chmod -R 755 "$MODEL_DIR"
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

start_docker_container() {
  # Configure directories
  DATA_DIR=$(configure_directory "data directory" "./data")
  TEMP_DIR=$(configure_directory "temp directory" "./tmp")
  MODEL_DIR=$(configure_directory "model cache directory" "$MODEL_DIR")
  LOG_DIR=$(configure_directory "logs directory" "./logs")

  # Set environment variables
  export TEMP_DIR="$TEMP_DIR"
  export DATA_DIR="$DATA_DIR"
  export LOG_DIR="$LOG_DIR"
  export MODEL_DIR="$MODEL_DIR"

  # check if there is one running container
  container_id=$(docker-compose ps -q)

  if [[ ! -z "$container_id" ]]; then
    echo "Stopping existing Docker container..."
    execute_command docker-compose down
  fi

  echo "Starting Docker container..."
  execute_command docker-compose up -d
}

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
  echo "Starting setup"
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
