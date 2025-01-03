# MotionCor2 Setup and Usage Guide

**MotionCor2** is a high-performance program for drift correction of cryo-EM movie frames. This guide will help you set up **MotionCor2** locally on your system, run the software for motion correction, and troubleshoot common issues.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Setting Up the Environment](#setting-up-the-environment)
4. [Running MotionCor2](#running-motioncor2)
5. [Run MotionCor Plugin](#run-motioncor-plugin)
6. [Results](#results)
7. [Installtion with Docker](#installation-with-docker)


---

## Prerequisites

Before you begin, ensure you have the following:

### 1. NVIDIA GPU:
   - MotionCor2 requires an **NVIDIA GPU** for GPU acceleration.
   - Ensure that your system has a supported **CUDA-compatible GPU**.

### 2. CUDA Toolkit and Drivers:
   - MotionCor2 relies on **CUDA** for GPU acceleration. You must install the appropriate **CUDA drivers** for your GPU.
   - Install **NVIDIA drivers** and **CUDA toolkit** following the instructions from the [NVIDIA website](https://developer.nvidia.com/cuda-downloads).

### 3. Software Dependencies:
   - Ensure that you have **gcc**, **g++**, and **make** installed for compiling and running CUDA programs.

### 4. MotionCor2 Software:
   - Download the MotionCor2 binaries **MotionCor2_1.6.4_Cuda121_Mar312023**. The program is available from the  official site, and it typically comes as a compressed file.

## Installation

### 1. Download Motioncor2
   - Obtain the MotionCor2 binaries from the official release page.
   - place the file in the root of the project **Magellon/plugins/magellon_motioncor_plugin/MotionCor2_1.6.4_Cuda121_Mar312023**

### 2. Ensure CUDA and GPU Drivers are installed:
   - After installing the necessary CUDA drivers, verify that your system can detect the GPU with the following command

   ```bash
   nvidia-smi
   ```
 - if there is no output then there is something wrong with the setup.

### 3. Download ctffind
   - Obtain the ctffind binaries from the official release page.
   - place the file in the root of the project **Magellon/plugins/magellon_motioncor_plugin/ctffind**

## Setting Up the Environment

## 1.  Set CUDA Environment Variables

To ensure that the system can access the necessary CUDA libraries, you need to update your environment variables.

For Linux (Ubuntu), add the following lines to your **.bashrc** or **.bash_profile**:

```bash
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/cuda-12.1/compat:$LD_LIBRARY_PATH
```
 - Add additional paths based on instructions from installation documentation

- After editing the file, refresh your environment variables with:

```bash
source ~/.bashrc  # or ~/.bash_profile
```

## 2. Verify CUDA Installation
To verify the CUDA installation, run:
```bash
nvcc --version
```
This should return the version of CUDA installed on your system.


## Running MotionCor2
Once your environment is set up, you can run MotionCor2 using the following command:

```bash
/path/to/MotionCor2_1.6.4_Cuda121_Mar312023 -InTiff /path/to/input_movie.tif -OutMrc /path/to/output_movie.mrc -Gain /path/to/gain_reference.tif 
```


## Run MotionCor Plugin

### 1. Run the rabbitMq
   - Make sure the docker is installed. Go to **support** folder in project and run the docker-compose file.

```bash
    docker-compose up
```

### 2. Create a Virtual environment
   - Ensure **conda** is installed on your machine.
   - Create a new conda environment
   ```bash
   conda create -n <environment-name>
   ```
   - Activate the environment
   ```bash
   conda activate <environment-name>
   ```

### 3. Check **build_motioncor3_command** in **utils.py** 
- If you need additional arguments to be supported you can uncomment the arguments or change them accordingly.
### 4. Steps to Run the Project
 - Install the project dependencies:
    ```bash
    pip install -r requirements.txt
    ```
 - Start the development server:
 ```bash
 uvicorn main:app --reload --port 8001
 ```

### 5.Run the test_publish.py file

 ```
 python3 test_publish.py
 ```

 - ensure check the path of the inputfile and gain file in the code.



 ## Results
  - **Five** files will be created in outputs folder inside gpfs with a unique **UUID**
    - <inputfilename>-Patch_Frame.log
    - <inputfilename>-Patch-Full.log
    - <inputfilename>-Patch-Patch.log
    - <outputfilename>_DW.mrc
    - <outputfilenamee>.mrc    


    

## Installation with Docker

### 1. Run the rabbitMq
   - Make sure the docker is installed. Go to **support** folder in project and run the docker-compose file.

```bash
    docker-compose up
```

### 2. Build the image
- Make sure you are in the root of the motioncor plugin and you will see a **Dockerfile** in it.
- Make sure you copy ctffind, movie file and Gain file in the same directory and add them in dockerfile too.

```bash
COPY 20241202_53597_gain_multi_ref.tif ./20241202_53597_gain_multi_ref.tif
COPY 20241203_54449_integrated_movie.mrc.tif ./20241203_54449_integrated_movie.mrc.tif
COPY ctffind ./ctffind
```

#### 1. Build the Image
```bash
docker build --tag motioncor .
```

#### 2. Run the container
```bash
docker run moioncor
```

#### 3. Run the test file
- go to bash inside the container
- Get the container id.

```bash
docker ps
```

- copy the id of the container
- run the bash 

```bash
docker exec -it <containerid> /bin/bash
```

- inside run the **test_publish.py** file
```bash
python3 test_publish.py
```

