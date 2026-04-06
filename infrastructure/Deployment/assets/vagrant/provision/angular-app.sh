#!/bin/bash

# Update apt-get and install Node.js
apt-get update
apt-get install -y curl
curl -sL https://deb.nodesource.com/setup_14.x | bash -
apt-get install -y nodejs

# Install Angular CLI
npm install -g @angular/cli
