# Use a base image with CUDA 12.1
ARG CUDA_IMAGE
ARG MOTIONCOR_BINARY
FROM --platform=linux/amd64 ${CUDA_IMAGE}

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
# ENV PATH=/usr/local/cuda/bin:$PATH
# ENV LD_LIBRARY_PATH=/usr/local/cuda-12/lib64:/usr/local/cuda-12/compat:$LD_LIBRARY_PATH


# Install required dependencies
RUN apt-get update && apt-get install -y \
    libc6 \
    libtiff-dev \
    curl \
    gnupg \
    software-properties-common \
    libpq-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    zlib1g-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    tcl8.6-dev \
    tk8.6-dev \
    python3-tk \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    libimagequant-dev \
    && rm -rf /var/lib/apt/lists/*

# Add deadsnakes PPA for Python 3.11
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-distutils \
    wget
WORKDIR /app
# Make python3.11 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Install pip using get-pip.py
RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python3.11 get-pip.py && \
    rm get-pip.py

# Install psycopg2-binary
RUN pip install psycopg2-binary

# Clear pip cache
RUN rm -rf /root/.cache/pip/*

# Set working directory


# Install other Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade -r ./requirements.txt
RUN ln -s /usr/lib/x86_64-linux-gnu/libtiff.so.5 /usr/lib/x86_64-linux-gnu/libtiff.so.6

# Install debugpy
RUN pip install --upgrade pip
RUN pip install debugpy

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PYTHONPATH=/app

# Copy application files
COPY configs/settings_dev.yml ./configs/settings_dev.yml
COPY configs/settings_prod.yml ./configs/settings_prod.yml
COPY core ./core
COPY service ./service
# COPY model.py ./model.py
COPY main.py ./main.py
COPY test_main.http ./
COPY test_publish.py ./test_publish.py
COPY utils.py ./utils.py
# COPY gpfs/20241202_53597_gain_multi_ref.tif ./gpfs/20241202_53597_gain_multi_ref.tif
# COPY gpfs/20241203_54449_integrated_movie.mrc.tif ./gpfs/20241203_54449_integrated_movie.mrc.tif


# Create a volume for the application data
VOLUME /gpfs
VOLUME /jobs

# Set the environment variable for the data directory
ENV APP_MODULE=main:app
ENV APP_ENV=production
# ENV CTF_ESTIMATION_FILE=/app/ctffind

# Expose port 80
EXPOSE 80

# Copy MotionCor2 binaries and libraries
COPY /motioncor2_binaryfiles/${MOTIONCOR_BINARY} ./${MOTIONCOR_BINARY}
COPY MotionCor3_1.0.1_Cuda121_10-26-2023 ./MotionCor3_1.0.1_Cuda121_10-26-2023
# Set executable permissions for MotionCor2
# RUN chmod +x /MotionCor2/MotionCor2

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
