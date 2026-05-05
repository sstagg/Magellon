# Build context = the unpacked .mpn archive (the v1 install pipeline's
# DockerInstaller hands us the archive root, not the parent repo).
# Everything we COPY must live INSIDE this archive — no parent-relative
# paths. The SDK comes from a wheel bundled under ./wheels/ rather than
# the source tree.
#
# For local dev with the docker-compose setup, build via:
#   docker build -f Dockerfile.dev -t magellon_fft_plugin .
# (a separate Dockerfile.dev can keep the parent-relative shape if needed).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev zlib1g-dev libtiff-dev libfreetype6-dev liblcms2-dev \
        libwebp-dev libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Wheel + requirements first so the Docker layer cache survives a
# code-only edit. ``./wheels/`` carries the magellon_sdk wheel that
# requirements.txt references.
COPY requirements.txt ./
COPY wheels ./wheels
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install prometheus-fastapi-instrumentator

# Plugin source. configs/ holds the YAML settings; core/, plugin/,
# main.py are the FastAPI + bus runtime entry points.
COPY configs ./configs
COPY core ./core
COPY plugin ./plugin
COPY main.py ./main.py

ENV PYTHONPATH=/app \
    APP_ENV=production

VOLUME /gpfs
VOLUME /jobs

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
