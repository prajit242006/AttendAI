FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Kolkata \
    FLASK_ENV=production \
    ATTENDAI_DATA_DIR=/data

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-cloud.txt ./
RUN pip install -r requirements-cloud.txt

COPY app ./app
COPY config.py cloud_app.py ./

# Keep one process: AttendAI stores its liveness challenges in memory.
# PORT is provided by Railway; 8080 is the local Docker fallback.
CMD ["sh", "-c", "exec gunicorn cloud_app:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 1 --timeout 120 --error-logfile -"]
