FROM ubuntu:latest

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    software-properties-common
# Add deadsnakes PPA for Python 3.11
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-distutils
# Make python3.11 the default python3
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
WORKDIR /app
# Install required packages
RUN apt-get install -y libpq-dev
    # libwxbase3.0-0v5 \
    # libwxbase3.0-dev \
    # libwxgtk3.0-0v5 \
    # libwxgtk3.0-dev \
    # wx3.0-headers \
    # wx-common \
    # libwxgtk-webview3.0-gtk3-0v5 \
    # libwxgtk-webview3.0-gtk3-dev \
    # libwxgtk-media3.0-0v5 \
    # libwxgtk-media3.0-dev \
    # libtiff5 \
    # libfftw3-single3 \
    # libomp-dev \
    # libpq-dev \
    # intel-mkl \
    # graphviz \
    # nano \
    # wget# Install pip
RUN apt-get install -y python3-pip
# Install psycopg2-binary
RUN pip install psycopg2-binary
# Clear pip cache
RUN rm -rf /root/.cache/pip/*
# Install other Python dependencies
COPY requirements.txt ./
RUN pip install  --upgrade -r ./requirements.txt
# Install debugpy
RUN pip install debugpy
# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1
# Copy application files
COPY appionlib ./appionlib
COPY assets ./assets
COPY configs ./configs
COPY configs/settings_dev.yml ./configs/settings_dev.yml
COPY configs/settings_prod.yml ./configs/settings_prod.yml
COPY core ./core
COPY pyami ./pyami
COPY service ./service
COPY main.py ./main.py
COPY ctffind ./ctffind
COPY ctffind_plot_results.sh ./ctffind_plot_results.sh
COPY test_main.http ./
COPY test_publish.py ./test_publish.py
COPY utils.py ./utils.py

# Create a volume for the application data
VOLUME /app/data
# VOLUME ./configs
# VOLUME /gpfs# Set the environment variable for the data directory
ENV DATA_DIR=/app/data
# Set environment variables for the app
ENV PYTHONPATH=/app
ENV APP_MODULE=main:app
ENV APP_ENV=production
ENV CTF_ESTIMATION_FILE=/app/ctffind
# Expose port 80
EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]