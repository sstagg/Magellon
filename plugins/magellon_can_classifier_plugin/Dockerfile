# Build context = the unpacked .mpn archive (the v1 install pipeline's
# DockerInstaller hands us the archive root, not the parent repo).
# Everything we COPY must live INSIDE this archive — no parent-relative
# paths. The SDK comes from a wheel bundled under ./wheels/.
#
# Phase 7b note (2026-05-03): the CAN algorithm uses torch on CUDA
# when available (compute_backend='torch-auto' or 'torch-cuda'); falls
# back to CPU torch for smaller stacks. This base image stays
# python:3.11-slim so CPU runs work without a GPU. For production GPU
# deployments swap to nvidia/cuda:12.1-runtime-ubuntu22.04 and install
# torch via:
#   pip install --extra-index-url https://download.pytorch.org/whl/cu121 \
#       torch>=2.0,<3.0
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Wheel + requirements first so the Docker layer cache survives a
# code-only edit. ./wheels/ carries the magellon_sdk wheel. torch
# dominates this layer's size — pinned to the CPU-only index in
# requirements.txt to avoid the ~3 GB CUDA-bundled default wheel.
#
# build-essential is installed for any source-build fallback then
# purged in the same RUN so it doesn't bloat the runtime layer; all
# pinned deps today ship manylinux wheels, but keeping the toolchain
# transient guards against a future pin slipping past wheel coverage.
COPY requirements.txt ./
COPY wheels ./wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install prometheus-fastapi-instrumentator \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /var/lib/apt/lists/*

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
