#!/bin/bash

# Update apt-get and install Flask dependencies
apt-get update
apt-get install -y python3-pip
pip3 install flask