# Build context MUST be the repo root (Docker/ compose uses `context: ..`).
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

# SDK source — requirements.txt installs -e ../../magellon-sdk
COPY magellon-sdk /app/magellon-sdk

WORKDIR /app/plugins/magellon_ptolemy_plugin
COPY plugins/magellon_ptolemy_plugin/requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt

COPY plugins/magellon_ptolemy_plugin/configs ./configs
COPY plugins/magellon_ptolemy_plugin/core ./core
COPY plugins/magellon_ptolemy_plugin/plugin ./plugin
COPY plugins/magellon_ptolemy_plugin/main.py ./main.py

ENV PYTHONPATH=/app/plugins/magellon_ptolemy_plugin \
    APP_ENV=production

VOLUME /gpfs
VOLUME /jobs

EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
