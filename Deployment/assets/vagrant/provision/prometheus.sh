#!/bin/bash

# Update apt-get and install Prometheus
apt-get update
wget https://github.com/prometheus/prometheus/releases/download/v2.32.1/prometheus-2.32.1.linux-amd64.tar.gz
tar -xzf prometheus-2.32.1.linux-amd64.tar.gz
mv prometheus-2.32.1.linux-amd64 /usr/local/bin/prometheus