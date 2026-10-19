FROM python:3.10-slim

# Install system dependencies required by OpenCV and PyTorch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download YOLOv8 Nano weights during build so container starts instantly
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

# Copy backend application
COPY backend/ ./backend/

ENV PORT=10000
EXPOSE 10000

# Run uvicorn dynamically binding to $PORT provided by Render
CMD ["sh", "-c", "uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-10000}"]
