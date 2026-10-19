FROM python:3.10-slim

# Install system dependencies required by OpenCV and PyTorch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Pre-install CPU-only PyTorch to prevent downloading 2.5GB+ CUDA wheels on Render
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy local YOLOv8 nano model weights if present and verify/download
COPY yolov8n.pt* ./
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copy backend application
COPY backend/ ./backend/

ENV PORT=10000
ENV PYTHONUNBUFFERED=1
EXPOSE 10000

# Run uvicorn dynamically binding to $PORT provided by Render
CMD ["sh", "-c", "exec uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-10000}"]

