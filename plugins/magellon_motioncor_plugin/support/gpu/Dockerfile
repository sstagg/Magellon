FROM nvidia/cuda:12.1.0-devel-ubuntu20.04

# Install Python and necessary packages
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install cupy
RUN pip3 install cupy-cuda12x
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY test_gpu.py .

CMD ["python3", "test_gpu.py"]
