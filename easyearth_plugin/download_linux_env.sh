#!/usr/bin/env bash

# Exit immediately on error
set -e

# Base directory (default to current directory if not set)
BASE_DIR="${BASE_DIR:-$(pwd)}"
echo "Using base directory: $BASE_DIR"

# Clone the easyearth_plugin repository (if needed)
# git clone https://github.com/YanCheng-go/easyearth_plugin.git  # Uncomment if needed!

# Check for gdown and install if missing
if ! command -v gdown &> /dev/null; then
    echo "gdown could not be found, installing..."
    pip install --user gdown
fi

# Google Drive file ID
FILE_ID="1FXmE_R1ZRoH3IHzv139stxNywB3HfgXo"
OUTPUT_FILE="easyearth_env.zip"

# Use gdown to download
echo "Downloading environment from Google Drive..."
gdown "https://drive.google.com/uc?id=${FILE_ID}" -O "${BASE_DIR}/${OUTPUT_FILE}"

# Unzip the environment
echo "Unzipping environment..."
unzip -o "${BASE_DIR}/${OUTPUT_FILE}" -d "${BASE_DIR}"

# Cleanup
rm "${BASE_DIR}/${OUTPUT_FILE}"

echo "Python env for linux system Download and extraction completed."
