FROM python:3.10-slim

# Install system dependencies
RUN apt-get update \
    && apt-get install -y \
    libexpat1 \
    libgdal-dev \
    gdal-bin --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Define environment variables for paths
ENV APP_DIR=/usr/src/app
ENV BASE_DIR=/usr/src/app/easyearth_base
ENV MODEL_CACHE_DIR=/usr/src/app/.cache/models

# Create required directories
RUN mkdir -p $MODEL_CACHE_DIR $BASE_DIR/embeddings $BASE_DIR/images $BASE_DIR/logs $BASE_DIR/predictions $BASE_DIR/tmp
WORKDIR $APP_DIR

# Copy only requirements first to leverage Docker cache
COPY requirements.txt $APP_DIR/

# upgrade pip
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt --upgrade

# Copy the application code
COPY . $APP_DIR/

EXPOSE 3781

CMD ["python", "-m", "easyearth.app", "--host", "0.0.0.0", "--port", "3781"]
