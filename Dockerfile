FROM python:3.10-slim

# Install system dependencies for OpenCV and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements
COPY requirements.txt .

# Install Python requirements + web dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt \
    fastapi \
    "uvicorn[standard]" \
    python-multipart \
    google-api-python-client \
    google-auth-httplib2 \
    google-auth-oauthlib \
    jinja2

# Copy the rest of the application
COPY . .

# Download the MediaPipe pose landmarker model bundle if not present
RUN mkdir -p models && \
    if [ ! -f models/pose_landmarker_lite.task ]; then \
        curl -sSL -o models/pose_landmarker_lite.task \
        https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task; \
    fi

EXPOSE 8000

ENV BOWLING_SECRET_KEY="bowling2026"
ENV PORT=8000

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
