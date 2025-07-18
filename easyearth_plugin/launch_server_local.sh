#!/bin/bash

# Virtual environment
echo "Using base directory: $BASE_DIR"
source "$BASE_DIR/easyearth_env/bin/activate"
export PATH="$BASE_DIR/easyearth_env/bin:$PATH" # Add virtual environment's python to PATH
PYTHON_CMD="$BASE_DIR/easyearth_env/bin/python"
echo "Current Python: $(which python)"
echo "Python version: $(python --version)"

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

echo "Created directories"

export USER_BASE_DIR=$BASE_DIR
export RUN_MODE=local
export PYTORCH_ENABLE_MPS_FALLBACK=1 # enables MPS fallback for PyTorch
cd "$BASE_DIR"
"$PYTHON_CMD" -m easyearth.app --host 0.0.0.0 --port 3781 # runs the application
