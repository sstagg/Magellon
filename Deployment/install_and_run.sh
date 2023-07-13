#!/bin/bash

# Check if Python 3 is already installed
if ! command -v python3 &> /dev/null; then
    # Update package manager
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
    elif command -v yum &> /dev/null; then
        sudo yum update
    fi

    # Install Python 3
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y python3
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3
    fi

    # Check if Homebrew package manager is installed
    if command -v brew &> /dev/null; then
        # Install Python 3 using Homebrew
        brew install python3
    fi

fi

# Install Python package dependencies
if command -v python3 &> /dev/null; then
    pip3 install -r requirements.txt
else
    echo "Python 3 is not installed. Aborting."
    exit 1
fi

# Run the main.py script
python3 main.py
