FROM ubuntu:latest

# Set non-interactive mode for apt-get
ENV DEBIAN_FRONTEND=noninteractive


RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    software-properties-common wget nano curl
# Add deadsnakes PPA for Python 3.11
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y
WORKDIR /app

# Update and install required packages
RUN apt-get update && \
    apt-get install -y wget bzip2 && \
    apt-get clean

#RUN wget https://repo.anaconda.com/archive/Anaconda3-2024.02-1-Linux-x86_64.sh
#RUN bash Anaconda3-2024.02-1-Linux-x86_64.sh

RUN mkdir -p /opt/conda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /opt/conda/miniconda.sh
RUN bash /opt/conda/miniconda.sh -b -u -p /opt/miniconda

RUN rm -rf /opt/conda
RUN /opt/miniconda/bin/conda init bash
# Add Miniconda to PATH
ENV PATH="/opt/miniconda/bin:$PATH"
RUN conda config --add channels conda-forge
# Echo the current shell
#RUN echo "The current shell is: $SHELL"

# Install required packages
#RUN apt-get install -y libpq-dev libjpeg-dev libopenjp2-7-dev
#RUN apt-get install -y libtiff5-dev libjpeg8-dev libopenjp2-7-dev zlib1g-dev \
#                           libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python3-tk \
#                           libharfbuzz-dev libfribidi-dev libxcb1-dev libimagequant-dev  libtiff-dev libtiff5-dev



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



# Install psycopg2-binary
RUN conda install psycopg2-binary

# Clear pip cache
RUN rm -rf /root/.cache/pip/*
# Install other Python dependencies
COPY requirements.txt ./
RUN conda install matplotlib
RUN conda install Pillow
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