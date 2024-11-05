
# 2D Classifier Application

The **2D Classifier** application provides a backend for processing model data and a frontend interface for user interactions. This document guides you on setting up and running the application using Docker Compose.

## Table of Contents
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Running the Application with Docker Compose](#running-the-application-with-docker-compose)
- [Environment Configuration](#environment-configuration)
- [Accessing the Application](#accessing-the-application)
- [Troubleshooting](#troubleshooting)

## Project Structure
The project has the following structure:
```
.
├── 2dclass_evaluator            # Model evaluator directory (mounted as a volume)
├── 2dclasswebtool
│   ├── 2dclassifierbackend      # Backend directory for model processing
│   │   ├── Dockerfile           # Dockerfile for backend service
│   │   └── ...                  # Additional backend files
│   └── 2dclassifierFrontend     # Frontend directory for user interface
│       ├── Dockerfile           # Dockerfile for frontend service
│       └── ...                  # React app files
├── docker-compose.yml           # Docker Compose configuration file
```

## Prerequisites
Ensure **Docker** and **Docker Compose** are installed:
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Running the Application with Docker Compose

The Docker Compose setup will build and start both the backend and frontend services.

### Steps

1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Start the Application**:
   Use the following command to build and start both services:
   ```bash
    UPLOADS_DIR=/Users/puneethreddymotukurudamodar/uploads BACKEND_URL=http://localhost:8000 docker-compose up --build
   ```

   This will:
   - Build the backend and frontend Docker images.
   - Start the backend on port **8000** and the frontend on port **3000**.

3. **Stop the Application**:
   To stop the services, press `CTRL + C` in the terminal where Docker Compose is running or run:
   ```bash
   docker-compose down
   ```

## Environment Configuration

The `docker-compose.yml` is set up to mount `2dclass_evaluator` as a volume in the backend container. Ensure the directory structure aligns with the `docker-compose.yml` paths:
```yaml
services:
  backend:
    build:
      context: ./2dclassifierbackend
      dockerfile: Dockerfile
    volumes:
      - ../2dclass_evaluator:/app/2dclass_evaluator
    ports:
      - "8000:8000"
  frontend:
    build:
      context: ./2dclassifierFrontend
      dockerfile: Dockerfile
      args:
        - REACT_APP_BACKEND_URL=${BACKEND_URL}
    ports:
      - "3000:80"
```

## Accessing the Application
- **Backend**: `http://localhost:8000`
- **Frontend**: `http://localhost:3000`

Access the frontend via a web browser at `http://localhost:3000`, which connects to the backend on `http://localhost:8000`.

## Troubleshooting
- Ensure Docker has enough allocated memory if running large models.
- Check ports 8000 and 3000 for conflicts with other services.
