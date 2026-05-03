# Build context MUST be the repo root (compose: `context: ..` from
# Docker/, `dockerfile: plugins/magellon_stack_maker_plugin/Dockerfile`).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/plugins/magellon_stack_maker_plugin
COPY plugins/magellon_stack_maker_plugin/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install prometheus-fastapi-instrumentator

COPY plugins/magellon_stack_maker_plugin/configs ./configs
COPY plugins/magellon_stack_maker_plugin/core ./core
COPY plugins/magellon_stack_maker_plugin/plugin ./plugin
COPY plugins/magellon_stack_maker_plugin/main.py ./main.py

ENV PYTHONPATH=/app/plugins/magellon_stack_maker_plugin \
    APP_ENV=production

VOLUME /gpfs
VOLUME /jobs

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
