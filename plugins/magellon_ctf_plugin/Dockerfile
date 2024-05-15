FROM ubuntu:latest
# Set non-interactive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    apt-file \
    software-properties-common curl wget nano
# Add deadsnakes PPA for Python 3.11
RUN add-apt-repository universe
RUN add-apt-repository multiverse


RUN apt update

# Add Debian Buster repository (temporarily) to install specific packages
RUN echo "deb [trusted=yes] http://ftp.de.debian.org/debian buster main contrib non-free" > /etc/apt/sources.list.d/buster.list && \
    apt-get update && \
    apt-get install -y libwxbase3.0-0v5 libtiff5 libfftw3-single3 libomp-dev && \
    apt-get install -y libwxbase3.0-0v5 libwxbase3.0-dev libwxgtk3.0-0v5 libwxgtk3.0-dev wx3.0-headers wx-common libwxgtk-webview3.0-gtk3-0v5 \
    libwxgtk-webview3.0-gtk3-dev libwxgtk-media3.0-0v5 libwxgtk-media3.0-dev wx3.0-i18n wx3.0-examples && \
    rm /etc/apt/sources.list.d/buster.list && \
    apt-get clean && \
    apt-get update

WORKDIR /app

#RUN wget https://repo.anaconda.com/archive/Anaconda3-2024.02-1-Linux-x86_64.sh
#RUN bash Anaconda3-2024.02-1-Linux-x86_64.sh

RUN mkdir -p /opt/conda
#RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /opt/conda/miniconda.sh
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-py39_24.3.0-0-Linux-x86_64.sh -O /opt/conda/miniconda.sh
RUN bash /opt/conda/miniconda.sh -b -u -p /opt/miniconda

RUN rm -rf /opt/conda
#RUN /opt/miniconda/bin/conda init bash
# Add Miniconda to PATH
ENV PATH="/opt/miniconda/bin:$PATH"
RUN export  PATH="/opt/miniconda/bin:$PATH"
RUN conda config --add channels conda-forge

RUN apt install -y intel-mkl

RUN conda install matplotlib==3.3.4
RUN conda install Pillow

# Clear pip cache
RUN rm -rf /root/.cache/pip/*
# Install other Python dependencies
COPY requirements.txt ./

RUN pip  install  --upgrade -r ./requirements.txt
# Install debugpy
RUN pip install --upgrade pip
RUN pip install debugpy
#RUN pip install logstash_formatter
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
