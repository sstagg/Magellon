#FROM continuumio/anaconda3
FROM ubuntu
#
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    apt-file \
    software-properties-common
#
#RUN apt-get update && \
#    apt-get upgrade -y && \
#    apt-get install -y \
#    build-essential \
#    cmake \
#    apt-file
#
#RUN apt-get update
#
#
#RUN curl -L http://repos.codelite.org/CodeLite.asc | apt-key add -
#RUN apt-add-repository 'deb http://repos.codelite.org/wx3.0.5/debian/ buster libs'
RUN apt-get update && \
    echo "deb http://ftp.de.debian.org/debian buster main contrib non-free" >> /etc/apt/sources.list && \
#    apt-add-repository 'deb http://ftp.de.debian.org/debian buster main' && \
    apt-get update && \
    apt-get install -y libwxbase3.0-0v5 libtiff5 libfftw3-single3 libomp-dev


#RUN apt-get install libwxbase3.0-0-unofficial \
#                 libwxbase3.0-dev \
#                 libwxgtk3.0-0-unofficial \
#                 libwxgtk3.0-dev

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y \
    intel-mkl
RUN apt-get install -y intel-mkl

#
#RUN apt-get update  \
# && apt-get upgrade  \
# && apt-get install -y -qq   bzip2 \
#                      cmake \
#                      cpio \
#                      curl \
#                      g++ \
#                      gcc \
#                      gfortran \
#                      git \
#                      gosu \
#                      libblas-dev \
#                      liblapack-dev \
#                      libopenmpi-dev \
#                      openmpi-bin \
#                      wget \
#                      zlib1g-dev \
#                      vim       \
#                      htop      \

#                      python3-dev \
#                      python3-pip \
#                      virtualenv \

RUN apt-get install -y libwxbase3.0-0v5 libwxbase3.0-dev libwxgtk3.0-0v5 libwxgtk3.0-dev wx3.0-headers wx-common libwxgtk-webview3.0-gtk3-0v5 libwxgtk-webview3.0-gtk3-dev libwxgtk-media3.0-0v5 libwxgtk-media3.0-dev wx3.0-i18n wx3.0-examples
#RUN apt-get install -y graphviz nano wget
RUN pip install psycopg2-binary --no-cache-dir

COPY requirements.txt ./
RUN pip install --no-cache-dir  --upgrade -r ./requirements.txt
#RUN pip3 install --no-cache-dir  -r ./requirements.txt
#RUN apt-get update &&  apt-get install -y gcc g++ git-svn
#    build-base
#    gcc \
#    git-svn \
#    gtk+3.0 \
#    g++ \
#    jpeg-dev \
#    libc-dev \
#    python-dev \
#    wxgtk \
#    wxgtk-dev \
#    zlib-dev

#Run pip install -f https://extras.wxpython.org/wxPython4/extras/linux/gtk3/centos-7 wxPython==4.0.0
#RUN pip install wxPython
RUN pip install debugpy

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE 1
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED 1

RUN which python3
#COPY . .
COPY appionlib ./appionlib
COPY assets ./assets
COPY configs ./configs
COPY configs/settings_dev.yml ./configs/settings_dev.yml
COPY configs/settings_prod.yml ./configs/settings_prod.yml
COPY core ./core
#COPY core/rabbitmq ./core/rabbitmq
COPY pyami ./pyami
COPY service ./service
COPY tests ./tests
COPY main.py ./main.py

#COPY core/logger_config.py ./core/logger_config.py
#COPY core/settings.py ./core/settings.py

COPY ctffind ./ctffind
COPY ctffind_plot_results.sh ./ctffind_plot_results.sh
COPY test_main.http ./
COPY test_publish.py ./test_publish.py
COPY utils.py ./utils.py


## Install SSH server
#RUN apt-get update && apt-get install -y openssh-server
#RUN mkdir /var/run/sshd
#
## Set root password (replace 'your_password' with your desired password)
#RUN echo 'root:your_password' | chpasswd
#
## Permit root login and allow password authentication
#RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
#RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
#
#EXPOSE 22



# Create a volume for the application data
VOLUME /app/data
VOLUME ./configs
VOLUME /gpfs

# Set the environment variable for the data directory
ENV DATA_DIR=/app/data

# Set environment variables for the app
ENV PYTHONPATH=/app
ENV APP_MODULE=main:app

ENV APP_ENV=production
ENV CTF_ESTIMATION_FILE=/app/ctffind

# Expose port 80
EXPOSE 80

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
#CMD ["python3", "-m", "debugpy", "--listen", "0.0.0.0:5678", "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "80"]