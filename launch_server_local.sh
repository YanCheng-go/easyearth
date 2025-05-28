#!/bin/bash

# Check if running on Mac
if [[ "$OSTYPE" != "darwin"* ]]; then
    REQUIREMENTS="requirements.txt"
else
    REQUIREMENTS="requirements_mac.txt"
fi

# Create virtual environment
# check if easyearth_env already exists
if [ ! -d "easyearth_env" ]; then
    echo "Creating virtual environment 'easyearth_env'..."
    python3 -m venv easyearth_env
    source easyearth_env/bin/activate
    pip install --upgrade pip
    pip install torch torchvision torchaudio
    pip install --prefer-binary -r $REQUIREMENTS
else
    echo "Virtual environment 'easyearth_env' already exists."
    source easyearth_env/bin/activate
fi

# Set up local directories and environment
export APP_DIR="$(pwd)"

# Ask user to input data directory
# If no input, use default
DATA_DIR="./data"
read -p "Enter the data directory (default: $DATA_DIR): " DATA_DIR
if [ -z "$DATA_DIR" ]; then
    DATA_DIR="./data"
fi
export EASYEARTH_DATA_DIR="$DATA_DIR"
# Set up temp and logs directories
export EASYEARTH_TEMP_DIR="$DATA_DIR/tmp"
mkdir -p "$TEMP_DIR"
export LOG_DIR="$DATA_DIR/logs"
mkdir -p "$LOG_DIR"

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
  export MODEL_CACHE_DIR="$USERPROFILE/.cache/easyearth/models"
else
  export MODEL_CACHE_DIR="$HOME/.cache/easyearth/models"
fi

# create model cache directory if it does not exist
mkdir -p "$MODEL_CACHE_DIR"

export PYTORCH_ENABLE_MPS_FALLBACK=1 # Enable MPS fallback for PyTorch

# Run the application
python -m easyearth.app --host 0.0.0.0 --port 3781
