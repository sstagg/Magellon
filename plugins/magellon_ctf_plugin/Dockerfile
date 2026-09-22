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

# Install the SDK from the repository source instead of the stale bundled
# wheel, so runtime fixes in magellon-sdk are included in the image.
COPY magellon-sdk /app/magellon-sdk
COPY plugins/magellon_ctf_plugin/requirements.docker.txt ./requirements.docker.txt
ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN python3 -m pip install --break-system-packages --no-cache-dir --force-reinstall --no-deps /app/magellon-sdk[rabbitmq,nats,logging,config] \
    && python3 -m pip install --break-system-packages --ignore-installed --no-cache-dir -r ./requirements.docker.txt
# Install debugpy
RUN python3 -m pip install --break-system-packages --no-cache-dir debugpy

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1
# Copy application files
COPY plugins/magellon_ctf_plugin/appionlib ./appionlib
COPY plugins/magellon_ctf_plugin/configs/settings_dev.yml ./configs/settings_dev.yml
COPY plugins/magellon_ctf_plugin/configs/settings_prod.yml ./configs/settings_prod.yml
COPY plugins/magellon_ctf_plugin/core ./core
COPY plugins/magellon_ctf_plugin/plugin ./plugin
COPY plugins/magellon_ctf_plugin/pyami ./pyami
COPY plugins/magellon_ctf_plugin/service ./service
COPY plugins/magellon_ctf_plugin/main.py ./main.py
COPY plugins/magellon_ctf_plugin/ctffind ./ctffind
COPY plugins/magellon_ctf_plugin/ctffind_plot_results.sh ./ctffind_plot_results.sh
COPY plugins/magellon_ctf_plugin/test_main.http ./
COPY plugins/magellon_ctf_plugin/test_publish.py ./test_publish.py
COPY plugins/magellon_ctf_plugin/utils.py ./utils.py
# Create a volume for the application data
#VOLUME /app/data
VOLUME /gpfs
VOLUME /jobs
# Set the environment variable for the data directory
#ENV DATA_DIR=/app/data
# Set environment variables for the app
ENV PYTHONPATH=/app
ENV APP_MODULE=main:app
ENV APP_ENV=production
ENV CTF_ESTIMATION_FILE=/app/ctffind
RUN chmod +x ./ctffind
# Expose the conventional plugin HTTP port used by CoreService's docker installer.
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

