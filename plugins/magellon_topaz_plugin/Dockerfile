# Build context MUST be the repo root (Docker/ compose uses `context: ..`).
#
# Multi-stage build, mirror of magellon_ptolemy_plugin/Dockerfile. Builder
# compiles wheels with dev headers; runtime ships only the runtime libs
# Pillow / numpy link against. No torch, no torchvision, no topaz-em —
# inference is onnxruntime-only.
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/plugins/magellon_topaz_plugin
COPY plugins/magellon_topaz_plugin/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type d -name tests -exec rm -rf {} + 2>/dev/null || true

# ==== runtime =================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/plugins/magellon_topaz_plugin \
    APP_ENV=production

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/plugins/magellon_topaz_plugin
COPY plugins/magellon_topaz_plugin/configs ./configs
COPY plugins/magellon_topaz_plugin/core ./core
COPY plugins/magellon_topaz_plugin/plugin ./plugin
COPY plugins/magellon_topaz_plugin/main.py ./main.py

VOLUME /gpfs
VOLUME /jobs

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
