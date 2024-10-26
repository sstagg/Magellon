# Start from a base image with Python 3.12
FROM python:3.12.4

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libhdf5-dev \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories within /app
RUN mkdir -p /app/uploads

# Copy the entire backend directory (including evaluator) into the container
COPY main.py /app/main.py
COPY utils.py /app/utils.py
COPY requirements.txt /app/requirements.txt
# COPY 2dclass_evaluator /app/2dclass_evaluator


# Install dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Expose port 8000 for FastAPI
EXPOSE 8000

# Define environment variable for the upload directory
ENV UPLOAD_DIR=/app/uploads

# Define a volume to persist uploaded files in uploads directory
VOLUME ["/app/uploads"]

# Start the FastAPI application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
