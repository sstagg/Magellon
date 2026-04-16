# Minimal GPU container for MotionCor2 — used by Batch, SageMaker Processing, and EC2 spot tests.
# SageMaker Async needs a different HTTP server wrapper (see ../test-2-sagemaker-async/).
FROM --platform=linux/amd64 nvidia/cuda:12.1.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

# Docker Desktop's bundled HTTP proxy is ~500 kB/s for http:// but ~6 MB/s for https://.
# Rewrite sources to HTTPS before apt-get update. ca-certificates is preinstalled in the CUDA base.
RUN sed -i 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g; s|http://security.ubuntu.com|https://security.ubuntu.com|g' /etc/apt/sources.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip \
      libtiff5 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/lib/x86_64-linux-gnu/libtiff.so.5 /usr/lib/x86_64-linux-gnu/libtiff.so.6

RUN pip3 install --no-cache-dir boto3==1.35.*

WORKDIR /app

# MotionCor2 binary (copied in from the plugin dir at build time — see build.sh)
COPY MotionCor2 /app/MotionCor2
RUN chmod +x /app/MotionCor2

COPY run_motioncor.py /app/run_motioncor.py

# Default entrypoint reads env vars (see run_motioncor.py for MOTIONCOR_* vars)
ENTRYPOINT ["python3", "/app/run_motioncor.py"]
