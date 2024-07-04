FROM ubuntu:latest

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    software-properties-common \
    libc6

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
RUN apt-get install -y libpq-dev libjpeg-dev libopenjp2-7-dev
RUN apt-get install -y libtiff5-dev libjpeg8-dev libopenjp2-7-dev zlib1g-dev \
                           libfreetype6-dev liblcms2-dev libwebp-dev tcl8.6-dev tk8.6-dev python3-tk \
                           libharfbuzz-dev libfribidi-dev libxcb1-dev libimagequant-dev  libtiff-dev libtiff5-dev

# Install pip
RUN apt-get install -y python3-pip

# Install psycopg2-binary
RUN pip install psycopg2-binary

# Clear pip cache
RUN rm -rf /root/.cache/pip/*

# Install other Python dependencies
COPY requirements.txt ./
RUN pip install  --upgrade -r ./requirements.txt
# Install debugpy
#RUN pip install --upgrade pip
RUN pip install debugpy

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1
# Copy application files
COPY appionlib ./appionlib
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
#VOLUME /app/data
VOLUME /app/gpfs
# Set the environment variable for the data directory
#ENV DATA_DIR=/app/data
# Set environment variables for the app
ENV PYTHONPATH=/app
ENV APP_MODULE=main:app
ENV APP_ENV=production
ENV CTF_ESTIMATION_FILE=/app/ctffind
# Expose port 80
EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]

