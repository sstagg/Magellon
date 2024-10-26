
# 2D Classifier Project

The 2D Classifier application is designed for users to interact with a backend model to obtain predictions, modify outputs, and retrain the model to enhance performance. This document provides step-by-step instructions on how to set up and run the project, either with Docker or without it.

---

## Table of Contents

- [Installation Without Docker](#installation-without-docker)
  - [Prerequisites](#prerequisites)
  - [Steps to Run the Project](#steps-to-run-the-project)
- [Configuration](#configuration)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)

---

## Installation Without Docker

### Prerequisites

1. Ensure **conda** is installed on your machine.
2. Clone the project repository to your local machine.
3. Copy 2d_class_evaluator folder inside 2dclassifierbackend folder.
4. Create a new conda environment with Python 3.12:

   ```bash
   conda create -n <environment-name> python=3.12
   ```

   **Example:**

   ```bash
   conda create -n magellon2DAssess python=3.12
   ```

5. Activate the environment:

   ```bash
   conda activate magellon2DAssess
   ```

### Steps to Run the Project

1. **Create an `.env` file** inside the `2dclassifierbackend` directory.
2. **Copy the contents** of `.env.dev` to `.env` file.
3. **Install the project dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Start the development server**:

   ```bash
   uvicorn main:app --reload --port 8001
   ```

---

## Configuration

- Ensure you have the appropriate `.env` files in place for both Docker and local installations.
- Set any necessary environment variables in `.env` as per your project requirements.

## Usage

- Access the app at `http://localhost:8000` if using Docker, or at `http://localhost:8001` for a local setup.
- Use the endpoints to interact with the model for predictions, modifications, and retraining.



