FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1 \
    libegl1 \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only Torch first to save space/memory
RUN pip install --no-cache-dir torch==2.1.0+cpu torchvision==0.16.0+cpu --extra-index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y opencv-python

# PRE-DOWNLOAD MiDaS model to avoid runtime download timeout
# This caches the model in the Docker image during build
RUN python -c "import torch; print('Downloading MiDaS model...'); model = torch.hub.load('intel-isl/MiDaS', 'MiDaS_small'); print('Model downloaded successfully!')"

# Copy application code
COPY api/ ./api/

# Expose port
EXPOSE 7860

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application with proper timeout and worker configuration
# --timeout 120: Allow 2 minutes for slow requests (model loading)
# --workers 1: Single worker to save memory on free tier
# --threads 2: Handle 2 concurrent requests per worker
CMD ["python", "-m", "gunicorn", \
    "--bind", "0.0.0.0:7860", \
    "--timeout", "120", \
    "--workers", "1", \
    "--threads", "2", \
    "--chdir", "api", \
    "index:app"]
