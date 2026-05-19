# Build context = the unpacked .mpn archive. The Docker installer builds
# from the archive root, so every COPY source must be inside this plugin
# package.

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

WORKDIR /app
COPY requirements.txt ./
COPY wheels ./wheels
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && find /usr/local/lib/python3.11 -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local/lib/python3.11 -type d -name tests -exec rm -rf {} + 2>/dev/null || true

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo libtiff6 libfreetype6 liblcms2-2 \
        libwebp7 libopenjp2-7 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_ENV=production

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /app
COPY configs ./configs
COPY core ./core
COPY plugin ./plugin
COPY main.py ./main.py

VOLUME /gpfs
VOLUME /jobs

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
