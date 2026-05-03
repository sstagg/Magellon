# Phase 7b (2026-05-03) — CUDA-capable build. The CAN algorithm uses
# torch on CUDA when available (compute_backend='torch-auto' or
# 'torch-cuda'); falls back to CPU torch for smaller stacks. Switch
# the base image to nvidia/cuda:12.1-runtime-ubuntu22.04 for GPU
# deployments — the line below stays python:3.11-slim so CI without
# a GPU can still build + run contract tests.
#
# To enable GPU: change the FROM line and install torch via:
#   pip install --extra-index-url https://download.pytorch.org/whl/cu121 \
#       torch>=2.0,<3.0
#
# Build context MUST be the repo root (compose: `context: ..` from
# Docker/, `dockerfile: plugins/magellon_can_classifier_plugin/Dockerfile`).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/plugins/magellon_can_classifier_plugin
COPY plugins/magellon_can_classifier_plugin/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install prometheus-fastapi-instrumentator

COPY plugins/magellon_can_classifier_plugin/configs ./configs
COPY plugins/magellon_can_classifier_plugin/core ./core
COPY plugins/magellon_can_classifier_plugin/plugin ./plugin
COPY plugins/magellon_can_classifier_plugin/main.py ./main.py

ENV PYTHONPATH=/app/plugins/magellon_can_classifier_plugin \
    APP_ENV=production

VOLUME /gpfs
VOLUME /jobs

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
