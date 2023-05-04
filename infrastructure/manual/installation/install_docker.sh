#!/bin/bash

# Load configuration variables
source config.sh

# Detect operating system
if [[ "$(uname -s)" == "Darwin" ]]; then
    # macOS
    echo "Detected macOS"
    if [[ $(which docker) ]]; then
        echo "Docker already installed"
    else
        echo "Installing Docker Desktop for Mac..."
        # Download and install Docker Desktop for Mac
        curl -L https://download.docker.com/mac/stable/Docker.dmg -o docker.dmg
        hdiutil mount docker.dmg
        sudo cp -R /Volumes/Docker/Docker.app /Applications/
        hdiutil unmount /Volumes/Docker
        rm docker.dmg
    fi
    # Install Docker Compose using pip
    if [[ $(which docker-compose) ]]; then
        echo "Docker Compose already installed"
    else
        echo "Installing Docker Compose..."
        sudo pip3 install docker-compose
    fi
    # Start Docker Desktop for Mac (if it's not already running)
    open -a Docker
elif [[ "$(cat /etc/os-release | grep ID)" == *"debian"* ]]; then
    # Debian-based systems (like Ubuntu)
    echo "Detected Debian-based system"
    # Install Docker using apt-get
    if [[ $(which docker) ]]; then
        echo "Docker already installed"
    else
        echo "Installing Docker..."
        sudo apt-get update
        sudo apt-get install -y docker.io
    fi
    # Install Docker Compose using pip
    if [[ $(which docker-compose) ]]; then
        echo "Docker Compose already installed"
    else
        echo "Installing Docker Compose..."
        sudo apt-get install -y python3-pip
        sudo pip3 install docker-compose
    fi
    # Enable and start Docker service
    sudo systemctl enable docker
    sudo systemctl start docker
elif [[ "$(cat /etc/os-release | grep ID)" == *"centos"* ]] || [[ "$(cat /etc/os-release | grep ID)" == *"rhel"* ]]; then
    # CentOS/RHEL-based systems
    echo "Detected CentOS/RHEL-based system"
    # Install Docker using yum
    if [[ $(which docker) ]]; then
        echo "Docker already installed"
    else
        echo "Installing Docker..."
        sudo yum install -y docker
    fi
    # Install Docker Compose using pip
    if [[ $(which docker-compose) ]]; then
        echo "Docker Compose already installed"
    else
        echo "Installing Docker Compose..."
        sudo yum install -y python3-pip
        sudo pip3 install docker-compose
    fi
    # Enable and start Docker service
    sudo systemctl enable docker
    sudo systemctl start docker
else
    echo "Error: unsupported operating system"
    exit 1
fi

# Log in to Docker (if username and password are provided in config.sh)
if [[ -n "$DOCKER_USERNAME" ]] && [[ -n "$DOCKER_PASSWORD" ]]; then
    echo "Logging in to Docker..."
    echo "$DOCKER_PASSWORD" | docker login --username "$DOCKER_USERNAME" --password-stdin
fi

# Add the current user to the docker group (so you don't need sudo to run Docker)
echo "Adding user to Docker group..."
sudo usermod -aG docker $USER
