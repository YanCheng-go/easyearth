#!/bin/bash

# Check if running on Mac
if [[ "$OSTYPE" != "darwin"* ]]; then
    REQUIREMENTS="requirements.txt"
else
    REQUIREMENTS="requirements_mac.txt"
fi

# Create virtual environment
python3 -m venv easyearth_env
source easyearth_env/bin/activate
pip install --upgrade pip
pip install torch torchvision torchaudio
pip install --prefer-binary -r $REQUIREMENTS

# Set up local directories and environment
export APP_DIR="$(pwd)"
export EASYEARTH_TEMP_DIR="$(pwd)/tmp"
export MODEL_CACHE_DIR="$HOME/.cache/easyearth/models"
export PYTORCH_ENABLE_MPS_FALLBACK=1 # Enable MPS fallback for PyTorch

# Run the application
python -m easyearth.app --host 0.0.0.0 --port 3781
