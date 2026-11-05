# ==========================================================
# Backend Dockerfile — FastAPI + OpenCV + MediaPipe
# ==========================================================
FROM python:3.11-slim

WORKDIR /app

# System dependencies required by OpenCV/MediaPipe for video I/O and image codecs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads models_store logs

EXPOSE 8000

# NOTE: accessing a physical webcam from inside a container requires
# passing --device=/dev/video0 (Linux) at `docker run` time; this is
# documented in the project README/installation guide. IP/RTSP camera
# sources work without any extra device passthrough.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
