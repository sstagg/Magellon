# syntax=docker/dockerfile:1
# Build context MUST be the repo root, not CoreService/ — requirements.txt
# pins `-e ../magellon-sdk`, which only resolves if we lay the project out
# in-image the same way it lives on disk:
#   /app/magellon-sdk
#   /app/CoreService
# (compose: `context: ..` from Docker/, `dockerfile: CoreService/Dockerfile`)
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    libpq-dev \
    build-essential \
    libffi-dev \
    graphviz \
    nano \
    wget \
 && rm -rf /var/lib/apt/lists/*

# SDK source first — pip's editable install in CoreService/requirements.txt
# points at this via `../magellon-sdk` (resolved from /app/CoreService).
COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/CoreService
COPY CoreService/requirements.txt ./

RUN pip3 install --upgrade pip \
 && pip install psycopg2-binary --no-cache-dir \
 && pip3 install --no-cache-dir --upgrade -r ./requirements.txt

COPY CoreService/main.py ./main.py
COPY CoreService/controllers ./controllers
COPY CoreService/lib ./lib
COPY CoreService/models ./models
COPY CoreService/repositories ./repositories
COPY CoreService/services ./services
COPY CoreService/templates ./templates
COPY CoreService/tests ./tests
COPY CoreService/configs ./configs
COPY CoreService/core ./core
COPY CoreService/static ./static
COPY CoreService/dependencies ./dependencies
COPY CoreService/domain ./domain
COPY CoreService/plugins ./plugins

COPY CoreService/configs/app_settings_dev.yaml ./configs/app_settings_dev.yaml
COPY CoreService/configs/app_settings_prod.yaml ./configs/app_settings_prod.yaml
COPY CoreService/logger_config.py ./logger_config.py
COPY CoreService/config.py ./config.py
COPY CoreService/database.py ./database.py
COPY CoreService/test_main.http ./

VOLUME /magellon
VOLUME ./configs
VOLUME /gpfs

ENV DATA_DIR=/app/CoreService/data \
    PYTHONPATH=/app/CoreService \
    APP_MODULE=main:app \
    APP_ENV=production

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
