#!/bin/bash

# Check operating system
if [[ "$OSTYPE" != "darwin"* ]]; then
    REQUIREMENTS="requirements.txt"
else
    REQUIREMENTS="requirements_mac.txt"
fi

# Virtual environment
if [ ! -d "easyearth_env" ]; then # checks if easyearth_env already exists
    echo "Creating virtual environment 'easyearth_env'..."
    python3 -m venv --copies easyearth_env
    source easyearth_env/bin/activate
    pip install --upgrade pip
    pip install torch torchvision torchaudio
    pip install --prefer-binary -r $REQUIREMENTS
else
    echo "Virtual environment 'easyearth_env' already exists."
    source easyearth_env/bin/activate
fi

# Set up directories
echo "Enter the full path to the folder where you want the 'easyearth_base' directory to be created. Or press 'Enter' if you want it to be created here ($(pwd))."
read -p "> " USER_INPUT
echo "You entered: $USER_INPUT"

if [ -z "$USER_INPUT" ]; then
    BASE_DIR="./easyearth_base"
else
    BASE_DIR="$USER_INPUT/easyearth_base"
fi

echo "Using base directory: $BASE_DIR"

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
  export MODEL_CACHE_DIR="$USERPROFILE/.cache/easyearth/models"
else
  export MODEL_CACHE_DIR="$HOME/.cache/easyearth/models"
fi

echo "Using model cache directory: $MODEL_CACHE_DIR"

mkdir -p "$MODEL_CACHE_DIR"
mkdir -p "$BASE_DIR/embeddings"
mkdir -p "$BASE_DIR/images"
mkdir -p "$BASE_DIR/logs"
mkdir -p "$BASE_DIR/predictions"
mkdir -p "$BASE_DIR/tmp"

export BASE_DIR="$BASE_DIR"
export PYTORCH_ENABLE_MPS_FALLBACK=1 # enables MPS fallback for PyTorch

python -m easyearth.app --host 0.0.0.0 --port 3781 # runs the application
