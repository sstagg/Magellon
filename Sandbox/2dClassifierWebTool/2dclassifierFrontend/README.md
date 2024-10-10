
# 2D Classifier Project

Welcome to the 2D Classifier project! This application allows users to interact with a backend model to obtain predictions, modify outputs, and retrain the model for better performance. This README will guide you through the installation process both using Docker and without it.

## Table of Contents

- [Installation Using Docker](#installation-using-docker)
  - [Build the Docker Image](#build-the-docker-image)
  - [Run the Docker Image](#run-the-docker-image)
- [Installation Without Docker](#installation-without-docker)
  - [Prerequisites](#prerequisites)
  - [Steps to Run the Project](#steps-to-run-the-project)

---

## Installation Using Docker

### Build the Docker Image

To build the Docker image, use the following command:

```bash
docker build --build-arg REACT_APP_BACKEND_URL={backendurl} -t {imagename} .
```

**Example:**

```bash
docker build --build-arg REACT_APP_BACKEND_URL=http://localhost:8001 -t 2dclassifierfrontend .
```

> **Note:** Make sure to replace `{backendurl}` with your actual backend URL. The `REACT_APP_BACKEND_URL` must be passed as an argument while building the image.

### Run the Docker Image

To run the Docker container, execute the following command:

```bash
docker run -d -p 80:80 2dclassifierfrontend
```

---

## Installation Without Docker

### Prerequisites

1. Ensure that **Node.js** is installed on your machine.
2. Clone the project repository to your local machine.

### Steps to Run the Project

1. **Create an `.env` file** inside the `2dclassifierFrontend` directory.
2. **Copy the contents** of `.env.dev to `.env` file.
3. **Install the project dependencies** using npm:

   ```bash
   npm install
   ```

4. **Start the development server**:

   ```bash
   npm start
   ```

---

