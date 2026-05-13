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

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Wheel + requirements first so the Docker layer cache survives a
# code-only edit. ``./wheels/`` carries the magellon_sdk wheel that
# requirements.txt references.
#
# build-essential + Pillow's dev headers are installed for any
# source-build fallback then purged in the same RUN so they don't
# bloat the runtime layer. Pillow at 10.4+ ships manylinux wheels so
# the headers aren't actually used by current pins; the runtime libs
# below survive (they're what Pillow's wheel binds against at import).
COPY requirements.txt ./
COPY wheels ./wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev zlib1g-dev libtiff-dev libfreetype6-dev liblcms2-dev \
        libwebp-dev libopenjp2-7-dev \
        libjpeg62-turbo libtiff6 libfreetype6 liblcms2-2 libwebp7 libopenjp2-7 \
    && pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install prometheus-fastapi-instrumentator \
    && apt-get purge -y --auto-remove \
        build-essential \
        libjpeg-dev zlib1g-dev libtiff-dev libfreetype6-dev liblcms2-dev \
        libwebp-dev libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

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
