# 2D Classifier Application and CryoSPARC/Relion Data Processing Script

This documentation provides guidance on setting up the **2D Classifier Application** and using the **CryoSPARC/Relion Data Processing Script** for model data processing and retraining.

## Table of Contents
1. [2D Classifier Application](#2d-classifier-application)
   - [Project Structure](#project-structure)
   - [Prerequisites](#prerequisites)
   - [Running the Application with Docker Compose](#running-the-application-with-docker-compose)
   - [Environment Configuration](#environment-configuration)
   - [Accessing the Application](#accessing-the-application)
   - [Troubleshooting](#troubleshooting)
2. [CryoSPARC and Relion Data Processing Script](#cryosparc-and-relion-data-processing-script)
   - [Overview](#overview)
   - [Input Requirements](#input-requirements)
     - [CryoSPARC Files](#cryosparc-files)
     - [Relion Files](#relion-files)
   - [Workflow](#workflow)
     - [Processing User Inputs](#processing-user-inputs)
     - [Updating Classification Values](#updating-classification-values)
   - [Data Conversion to HDF5](#data-conversion-to-hdf5)
     - [CryoSPARC Conversion](#cryosparc-conversion)
     - [Relion Conversion](#relion-conversion)
   - [Outputs](#outputs)
   - [Folder Naming Conventions](#folder-naming-conventions)
   - [Notes](#notes)

---

## 2D Classifier Application

### Project Structure
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

### Prerequisites
- **Docker**: [Install Docker](https://docs.docker.com/get-docker/)  
- **Docker Compose**: [Install Docker Compose](https://docs.docker.com/compose/install/)

### Running the Application with Docker Compose
#### Steps:
1. **Clone the Repository**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Start the Application**:
   ```bash
   UPLOADS_DIR=/Users/puneethreddymotukurudamodar/uploads BACKEND_URL=http://localhost:8000 docker-compose up --build
   ```

   - **Backend**: Runs on port **8000**.
   - **Frontend**: Runs on port **3000**.

3. **Stop the Application**:
   ```bash
   docker-compose down
   ```

### Environment Configuration
Ensure the `docker-compose.yml` correctly mounts `2dclass_evaluator` as a volume in the backend container.

Example `docker-compose.yml` snippet:
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
```

### Accessing the Application
- **Backend**: `http://localhost:8000`
- **Frontend**: `http://localhost:3000`

Access the frontend via a web browser at `http://localhost:3000`, which connects to the backend on `http://localhost:8000`.

### Troubleshooting
- Ensure Docker has enough allocated memory if running large models.
- Check ports 8000 and 3000 for conflicts with other services.

---

## CryoSPARC and Relion Data Processing Script

### Overview
This script processes classification outputs from **CryoSPARC** and **Relion**, manages user uploads, updates classification values, and converts data into `.hdf5` files for model retraining.

### Input Requirements

#### CryoSPARC Files
Users must upload the following files in a folder:
- `class_avg.cs`
- `class_avg.mrc`
- `particles.cs`
- `job.json`

#### Relion Files
Users must upload the following files in a folder:
- `classes.mrcs` → Renamed to `run_classes.mrcs` by the script.
- `model.star` → Renamed to `run_model.star` by the script.

### Workflow

#### Processing User Inputs
- **Folder Setup**: The folder name must start with `cryo_` or `relion_` followed by a UUID.
  - Example: `cryo_1234abcd`, `relion_5678efgh`
- When required files are uploaded, an `outputs` folder is created inside the respective folder to store generated outputs.

#### Updating Classification Values
- Users can send updated classification values via the `/update` endpoint.
- A file `updatedvalues.json` is created, containing both old and new classification values.

### Data Conversion to HDF5

#### CryoSPARC Conversion
1. **Extract Data**: Images and metadata are extracted from input files (`class_avg.cs`, `particles.cs`).
2. **Database Creation**: A SQLite database (`database.db`) is created and populated with:
   - Extracted images and metadata.
   - New classification values from `updatedvalues.json`.
3. **HDF5 Generation**: The `.hdf5` file is created using images, metadata, and the database.

#### Relion Conversion
1. **Rename Input Files**:
   - `classes.mrcs` → `run_classes.mrcs`
   - `model.star` → `run_model.star`
2. **Generate Additional Files**:
   - `job_score.txt`
   - `backup_selection.star`
3. **HDF5 Generation**: The `.hdf5` file is created using the renamed files and generated supporting files.

### Outputs
- A `.hdf5` file is generated for each processed folder:
  - **CryoSPARC**: Includes extracted data and updated classification values.
  - **Relion**: Includes renamed files and generated supporting files.

### Folder Naming Conventions
- CryoSPARC folders: `cryo_<UUID>`  
  Example: `cryo_1234abcd`
- Relion folders: `relion_<UUID>`  
  Example: `relion_5678efgh`

### Notes
- Ensure all required files are uploaded correctly.
- Folder names must follow the specified naming convention.
- Missing or incorrectly named files may result in processing errors.
