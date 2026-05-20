# Magellon Installation Guide

This guide covers installing Magellon CoreService and its plugins using Docker Compose on a Linux or Windows host.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Directory structure](#2-directory-structure)
3. [Clone the repository](#3-clone-the-repository)
4. [Configure the environment file](#4-configure-the-environment-file)
5. [Configure CoreService](#5-configure-coreservice)
6. [Plugin-specific setup](#6-plugin-specific-setup)
7. [Start the stack](#7-start-the-stack)
8. [Verify the installation](#8-verify-the-installation)
9. [Port reference](#9-port-reference)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

| Requirement | Minimum version | Notes |
|---|---|---|
| Docker Engine | 24+ | Docker Desktop is fine for dev |
| Docker Compose | v2 plugin (`docker compose`) | Included with Docker Desktop |
| Git | any | for cloning |
| NVIDIA driver | 525+ | **MotionCor plugin only** |
| NVIDIA Container Toolkit | latest | **MotionCor plugin only** — install via `nvidia-ctk` |

On Ubuntu, install the NVIDIA Container Toolkit with:
```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 2. Directory structure

Magellon uses three host directories that are mounted into every container. Decide on the root paths before starting.

| Variable | Default example | Purpose |
|---|---|---|
| `MAGELLON_GPFS_PATH` | `/opt/magellon/gpfs` | Shared data plane: images, CTF results, motion-corrected MRCs, etc. |
| `MAGELLON_HOME_PATH` | `/opt/magellon/home` | Per-session home trees (mirrors GPFS `home/`) |
| `MAGELLON_JOBS_PATH` | `/opt/magellon/jobs` | Plugin job working directories |

Create them before starting Docker:
```bash
sudo mkdir -p /opt/magellon/gpfs /opt/magellon/home /opt/magellon/jobs
sudo chown -R $USER /opt/magellon
```

On Windows (Docker Desktop with WSL2):
```
C:\magellon\gpfs
C:\magellon\home
C:\magellon\jobs
```

---

## 3. Clone the repository

```bash
git clone https://github.com/magellon/magellon.git
cd magellon
```

The relevant subdirectories:

```
magellon/
  CoreService/          # FastAPI backend
  Docker/               # docker-compose.yml + .env template + setup scripts
  plugins/
    magellon_ctf_plugin/
    magellon_fft_plugin/
    magellon_motioncor_plugin/
    magellon_fft_plugin/
    magellon_ptolemy_plugin/
    magellon_topaz_plugin/
    magellon_stack_maker_plugin/
    magellon_can_classifier_plugin/
    magellon_template_picker_plugin/
    magellon_result_processor/
  magellon-react-app/   # React frontend
  magellon-sdk/         # Shared Python SDK (installed as editable dep)
```

---

## 4. Configure the environment file

All Docker Compose variables are read from `Docker/.env`. Copy the template and edit it:

```bash
cd Docker
cp .env.example .env
nano .env        # or your preferred editor
```

### 4.1 Path settings

```dotenv
# Host paths — must exist before starting
MAGELLON_GPFS_PATH=/opt/magellon/gpfs
MAGELLON_HOME_PATH=/opt/magellon/home
MAGELLON_JOBS_PATH=/opt/magellon/jobs

# Windows example (Docker Desktop):
# MAGELLON_GPFS_PATH=C:\magellon\gpfs
# MAGELLON_HOME_PATH=C:\magellon\home
# MAGELLON_JOBS_PATH=C:\magellon\jobs
```

### 4.2 Database

```dotenv
MYSQL_DATABASE=magellon01
MYSQL_ROOT_PASSWORD=change_me          # used by root account
MYSQL_USER=magellon_user               # optional non-root user
MYSQL_PASSWORD=change_me
MYSQL_PORT=3306                        # host-side port (container always 3306)
```

### 4.3 RabbitMQ

```dotenv
RABBITMQ_DEFAULT_USER=rabbit
RABBITMQ_DEFAULT_PASS=change_me
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672
```

### 4.4 Application ports

```dotenv
MAGELLON_FRONTEND_PORT=8080            # React UI
MAGELLON_BACKEND_PORT=8000             # FastAPI (CoreService)
MAGELLON_RESULT_PLUGIN_PORT=8030
MAGELLON_CTF_PLUGIN_PORT=8035
MAGELLON_FFT_PLUGIN_PORT=8036
MAGELLON_MOTIONCOR_PLUGIN_PORT=8037
MAGELLON_PTOLEMY_PLUGIN_PORT=8038
MAGELLON_TOPAZ_PLUGIN_PORT=8039
MAGELLON_STACK_MAKER_PLUGIN_PORT=8040
MAGELLON_CAN_CLASSIFIER_PLUGIN_PORT=8041
MAGELLON_TEMPLATE_PICKER_PLUGIN_PORT=8042
```

### 4.5 Dragonfly (Redis-compatible cache)

```dotenv
DRAGONFLY_PORT=6379
DRAGONFLY_PASSWORD=change_me
```

### 4.6 Grafana

```dotenv
GRAFANA_USER_NAME=admin
GRAFANA_USER_PASS=change_me
```

### 4.7 MotionCor plugin (GPU only)

```dotenv
# Base CUDA image for the MotionCor container
CUDA_IMAGE=nvidia/cuda:12.1.1-runtime-ubuntu22.04

# Filename of the MotionCor2 binary inside plugins/magellon_motioncor_plugin/motioncor2_binaryfiles/
# You must supply this binary yourself (not redistributed in the repo).
MOTIONCOR_BINARY=MotionCor2_1.6.4_Cuda121_Mar312023
```

---

## 5. Configure CoreService

CoreService reads `CoreService/configs/app_settings_prod.yaml` when `APP_ENV=production` (set by Docker Compose). Edit this file to match your deployment.

### 5.1 Database connection

```yaml
database_settings:
  DB_Driver: mysql+pymysql
  DB_HOST: mysql              # container name — do not change for Docker
  DB_NAME: magellon01
  DB_USER: root
  DB_PASSWORD: change_me      # must match MYSQL_ROOT_PASSWORD in .env
  DB_Port: 3306
```

### 5.2 RabbitMQ connection

```yaml
rabbitmq_settings:
  HOST_NAME: rabbitmq         # container name — do not change for Docker
  PORT: 5672
  USER_NAME: rabbit
  PASSWORD: change_me         # must match RABBITMQ_DEFAULT_PASS in .env
```

### 5.3 Directory paths

These are **container-internal** paths (they match the volume mount targets in `docker-compose.yml`). You typically do not need to change them.

```yaml
directory_settings:
  MAGELLON_GPFS_PATH: /gpfs   # matches -v ${MAGELLON_GPFS_PATH}:/gpfs
  MAGELLON_HOME_DIR: home     # relative to GPFS root
  MAGELLON_JOBS_DIR: jobs
  PLUGINS_DIR: plugins        # plugin install state lives here
  PLUGIN_PACKAGES_DIR: plugin_packages
```

### 5.4 Security token (first-run setup)

The first time CoreService starts, a `/setup` endpoint is available to seed the admin account and initial configuration. Protect it with a token:

```yaml
security_setup_settings:
  ENABLED: true
  SETUP_TOKEN: replace_with_a_secret_string
  AUTO_DISABLE: true          # disables /setup after the first successful call
```

Set `AUTO_DISABLE: true` in production so the endpoint cannot be re-used.

### 5.5 Leginon database (optional)

If importing from an existing Leginon installation:

```yaml
leginon_db_settings:
  ENABLED: true
  HOST: host.docker.internal  # or the Leginon DB server IP
  PORT: 3310
  USER: usr_object
  PASSWORD: change_me
  DATABASE: dbemdata
```

Set `ENABLED: false` if you are not using Leginon.

### 5.6 Plugin Hub

```yaml
hub_settings:
  HUB_URL: https://magellon.org   # public catalog
  HUB_TIER: verified              # "verified" or "" (community)
```

For air-gapped sites: point `HUB_URL` at an internal mirror and set `HUB_TIER: ""`.

---

## 6. Plugin-specific setup

Each plugin has its own `configs/settings_prod.yml` under `plugins/<plugin_name>/`. The settings that matter are:

| Key | What to set |
|---|---|
| `database_settings.DB_HOST` | `mysql` (container name — do not change for Docker) |
| `database_settings.DB_PASSWORD` | Match `MYSQL_ROOT_PASSWORD` |
| `rabbitmq_settings.HOST_NAME` | `rabbitmq` |
| `rabbitmq_settings.PASSWORD` | Match `RABBITMQ_DEFAULT_PASS` |
| `MAGELLON_GPFS_PATH` | `/gpfs` (container-internal — do not change) |

### 6.1 CTF plugin (`magellon_ctf_plugin`)

No additional requirements. Uses `ctffind` bundled in the image.

```yaml
# configs/settings_prod.yml
PORT_NUMBER: 8035
MAGELLON_GPFS_PATH: /gpfs
JOBS_DIR: /gpfs/jobs
```

### 6.2 FFT plugin (`magellon_fft_plugin`)

No additional requirements. Pure-Python NumPy/SciPy FFT.

### 6.3 MotionCor plugin (`magellon_motioncor_plugin`)

**Requires a GPU and the MotionCor2 binary.**

1. Obtain the `MotionCor2` binary from the [UCSF MotionCor2 website](https://emcore.ucsf.edu/ucsf-software). The binary is not redistributed in this repository.
2. Place the binary in `plugins/magellon_motioncor_plugin/motioncor2_binaryfiles/` with the exact filename you set for `MOTIONCOR_BINARY` in `.env`.
3. Confirm Docker can access the GPU:
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
   ```
   This must succeed before starting the stack.

Minimum GPU memory: **11 GB** (a T4 / RTX 3080 or better). Cards with less memory may silently OOM-kill the binary.

### 6.4 Ptolemy plugin (`magellon_ptolemy_plugin`)

Detects holes and squares in cryo-EM atlas images. CPU-only. No additional setup beyond the common settings.

### 6.5 Stack Maker plugin (`magellon_stack_maker_plugin`)

Extracts particles from micrographs using picker coordinates. CPU-only. Requires the common settings.

### 6.6 CAN Classifier plugin (`magellon_can_classifier_plugin`)

2D classification using a CAN (Capsule/Attention Network) topology. By default runs on CPU. For GPU acceleration, change the `FROM` line in `plugins/magellon_can_classifier_plugin/Dockerfile` to:

```dockerfile
FROM nvidia/cuda:12.1-runtime-ubuntu22.04
```

and add a `deploy.resources.reservations.devices` GPU block to its service in `docker-compose.yml` (same pattern as the MotionCor service).

### 6.7 Template Picker plugin (`magellon_template_picker_plugin`)

Performs template-based particle picking. CPU-only. No additional setup.

---

## 7. Start the stack

```bash
cd Docker

# Build images and start all services
docker compose up -d --build

# Follow startup logs (Ctrl-C to detach)
docker compose logs -f backend
```

On Windows (PowerShell):
```powershell
cd C:\projects\magellon\Docker
docker compose up -d --build
```

**First-start note:** MySQL initialises from `magellon01db.sql` on the first run. This takes 30–60 seconds. `backend` will retry the DB connection until it succeeds; this is expected.

To start only infrastructure (MySQL + RabbitMQ + NATS + Dragonfly) and omit the heavier plugin builds during initial testing:

```bash
docker compose up -d mysql rabbitmq nats dragonfly
docker compose up -d backend web
```

---

## 8. Verify the installation

### 8.1 Check all containers are running

```bash
docker compose ps
```

Expected state: all services `running` (MySQL and RabbitMQ may show `starting` for the first ~60 s).

### 8.2 Open the UI

Navigate to `http://localhost:8080/en/panel/sessions`.

### 8.3 Check CoreService health

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

### 8.4 RabbitMQ management console

Open `http://localhost:15672` — log in with `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS`.
You should see the task queues (ctf_tasks_queue, fft_tasks_queue, etc.) listed after the first plugin starts.

### 8.5 Grafana

Open `http://localhost:3000` — log in with `GRAFANA_USER_NAME` / `GRAFANA_USER_PASS`.

### 8.6 API docs

Open `http://localhost:8000/docs` to browse and test the REST API directly.

---

## 9. Port reference

| Port | Service | Notes |
|---|---|---|
| 8080 | React frontend | Main user interface |
| 8000 | CoreService (FastAPI) | REST API, Socket.IO |
| 3306 | MySQL | Bound to 127.0.0.1 only |
| 5672 | RabbitMQ AMQP | Bound to 127.0.0.1 only |
| 15672 | RabbitMQ management UI | |
| 4222 | NATS | JetStream enabled |
| 6379 | Dragonfly (Redis) | Bound to 127.0.0.1 only |
| 9090 | Prometheus | |
| 3000 | Grafana | |
| 8030 | Result processor plugin | |
| 8035 | CTF plugin | |
| 8036 | FFT plugin | |
| 8037 | MotionCor plugin | |
| 8038 | Ptolemy plugin | |
| 8039 | Topaz plugin | |
| 8040 | Stack Maker plugin | |
| 8041 | CAN Classifier plugin | |
| 8042 | Template Picker plugin | |

All ports bind to `127.0.0.1` (localhost) by default. To expose them on a network interface, change the binding in `.env` or `docker-compose.yml`.

---

## 10. Troubleshooting

### MySQL fails to start

Check file permissions on the init SQL and data directory:
```bash
ls -la /opt/magellon  # Linux: owner should be 999:999 (MySQL container UID)
sudo chown -R 999:999 /opt/magellon/services/mysql
```

Or check if an old MySQL volume has conflicting data:
```bash
docker volume ls | grep mysql
docker volume rm <old_volume>   # data loss — only if you need a fresh DB
```

### Port already in use

```bash
# Linux
sudo lsof -i :8080

# Windows PowerShell
netstat -ano | findstr :8080
```

Change the conflicting port in `.env` (e.g. `MAGELLON_FRONTEND_PORT=8081`).

### MotionCor plugin: GPU not found

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-runtime-ubuntu22.04 nvidia-smi
```

If this fails: verify NVIDIA Container Toolkit is installed and `docker info | grep Runtimes` includes `nvidia`.

### Backend cannot connect to MySQL

The backend retries for ~60 s at startup. If it keeps failing:

1. Confirm `DB_PASSWORD` in `CoreService/configs/app_settings_prod.yaml` matches `MYSQL_ROOT_PASSWORD` in `.env`.
2. Check `docker compose logs mysql` for init errors.
3. Confirm the MySQL container is on the `magellon-network` subnet (172.16.238.7).

### Plugin does not consume tasks

1. Open the RabbitMQ UI (`http://localhost:15672`) and confirm the relevant queue exists (e.g. `ctf_tasks_queue`).
2. Check `docker compose logs magellon_ctf_plugin` for connection errors.
3. Confirm `rabbitmq_settings.PASSWORD` in the plugin's `configs/settings_prod.yml` matches `RABBITMQ_DEFAULT_PASS` in `.env`.

### Rebuild a single service after code changes

```bash
docker compose up -d --build backend         # CoreService only
docker compose up -d --build magellon_ctf_plugin
```

### Force a full clean rebuild

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```
