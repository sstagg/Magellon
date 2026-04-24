# Build context MUST be the repo root (Docker/ compose uses `context: ..`).
#
# Multi-stage: builder compiles wheels with dev headers, runtime copies the
# installed site-packages to a fresh slim image with ONLY the runtime libs
# Pillow / numpy / scipy link against. Drops the dev-header / build-tool
# payload (~200 MB) and keeps the image lean.

# ==== builder =================================================================
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev zlib1g-dev libtiff-dev libfreetype6-dev liblcms2-dev \
        libwebp-dev libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/plugins/magellon_ptolemy_plugin
COPY plugins/magellon_ptolemy_plugin/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type d -name tests -exec rm -rf {} + 2>/dev/null || true

# ==== runtime =================================================================
FROM python:3.11-slim

# Only the runtime shared libraries Pillow / scipy / etc link against — no
# -dev headers, no build-essential. Names are the Debian-13 (trixie) ones
# that python:3.11-slim is built on.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo libtiff6 libfreetype6 liblcms2-2 \
        libwebp7 libopenjp2-7 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/plugins/magellon_ptolemy_plugin \
    APP_ENV=production

# Bring over the installed Python packages + any console_scripts uvicorn ships.
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/plugins/magellon_ptolemy_plugin
COPY plugins/magellon_ptolemy_plugin/configs ./configs
COPY plugins/magellon_ptolemy_plugin/core ./core
COPY plugins/magellon_ptolemy_plugin/plugin ./plugin
COPY plugins/magellon_ptolemy_plugin/main.py ./main.py

VOLUME /gpfs
VOLUME /jobs

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
