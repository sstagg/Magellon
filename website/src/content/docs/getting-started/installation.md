---
title: Installation Guide
description: Dockerized installation of Magellon — dependency-free setup across platforms.
---

import { Aside, Steps } from '@astrojs/starlight/components';

<Aside type="note" title="Important">
This guide covers the Dockerized installation of Magellon. For non-Docker installations, refer to the standard installation guide.
</Aside>

This documentation walks you through installing and configuring Magellon using Docker. The Dockerized version simplifies dependency management and ensures consistent performance across different environments.

<Steps>

1. ### Install Docker

    Docker Desktop is the recommended installation method as it provides a consistent experience across platforms.

    - Download and install [Docker Desktop](https://docs.docker.com/desktop/) for your operating system.
    - Verify installation by running `docker --version` in your terminal.

2. ### Download the Demo Data

    Access the demo dataset using the Globus file transfer service.

    - Navigate to the [Globus File Manager](https://app.globus.org/file-manager?origin_id=4ad48aa4-a13a-4a8e-9a2b-da29eafbd3f9&origin_path=%2F).
    - Log in or create a Globus account if needed.
    - Transfer the demo files to your local system.

3. ### Download Magellon Source Code

    Clone the Magellon repository from GitHub:

    ```bash
    git clone https://github.com/sstagg/Magellon.git
    ```

    Alternatively, download the ZIP archive from the [GitHub repository](https://github.com/sstagg/Magellon).

4. ### Create Magellon Directories

    Magellon requires three main data directories plus a services directory. The simplest path is to copy the `magellon` directory under `docker/` to wherever you want it — it already contains the expected layout.

    - **Home Directory** — where Magellon stores generated files (e.g. `/magellon/home`).
    - **GPFS Directory** — for data imports, mapped to `/gpfs` internally (e.g. `/magellon/gpfs`).
    - **Jobs Directory** — for temporary file storage (e.g. `/magellon/jobs`).

    ```
    magellon/
    ├── home/
    ├── gpfs/
    ├── jobs/
    └── services/
    ```

5. ### Configure Environment Settings

    Navigate to the `Docker` subdirectory in the Magellon source, then:

    ```bash
    cp .env.example .env
    ```

    Edit `.env` to point at your Magellon directories:

    ```bash
    MAGELLON_HOME_PATH=/magellon/home
    MAGELLON_GPFS_PATH=/magellon/gpfs
    MAGELLON_JOBS_PATH=/magellon/jobs
    ```

6. ### Start Magellon Containers

    From the `Docker` directory:

    ```bash
    bash start.sh
    ```

    Wait for container initialization (longer on first run). For subsequent starts:

    ```bash
    docker compose --profile default up -d
    ```

    <Aside type="note" title="First Run Performance">
    The first run downloads and initializes every supporting container — this can take a while on slow networks. Subsequent starts are much faster.
    </Aside>

7. ### Import Demo Data

    - Move the Globus demo data into your Magellon GPFS directory.
    - Open the front-end at [http://localhost:8080/en/panel/images](http://localhost:8080/en/panel/images).
    - Click **Login**, then the menu icon in the top-left.
    - Select **Import** and open the **Magellon import** tab.
    - Double-click the `24dec03a` directory, then `session.json`.
    - Click **IMPORT DATA** to start the import.

    <Aside type="caution" title="Import Processing Time">
    Import can take 5–60 minutes depending on system resources. On Linux with a compatible GPU, Magellon performs frame alignment, which can extend the processing time.
    </Aside>

8. ### Explore Magellon

    Navigate to [http://localhost:8080/en/panel/images](http://localhost:8080/en/panel/images) and select the imported session (e.g. `24DEC03A`) to begin exploring your data.

</Steps>
