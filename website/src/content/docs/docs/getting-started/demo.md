---
title: Demo Walkthrough
description: Run Magellon end-to-end against the bundled demo dataset.
---

import { Aside, Steps } from '@astrojs/starlight/components';

This walkthrough mirrors the original Magellon demo post — install Docker, fetch the demo data, start the stack, and import a session.

<Steps>

1. ### Install Docker

    On Linux without root, ask a system administrator to install Docker and add you to the `docker` group.

    Verify with:

    ```bash
    docker --version
    ```

2. ### Determine your CUDA version

    Required for motion correction. On Linux:

    ```bash
    nvidia-smi
    ```

    Note the CUDA version reported in the top-right corner — you'll pass it to the start script.

3. ### Download the demo data via Globus

    Open the [Globus File Manager](https://app.globus.org/file-manager?origin_id=4ad48aa4-a13a-4a8e-9a2b-da29eafbd3f9&origin_path=%2F), sign in, and transfer the demo files to your machine.

4. ### Get the Magellon source

    Clone the release branch:

    ```bash
    git clone https://github.com/sstagg/Magellon.git
    cd Magellon
    ```

5. ### Create a processing directory

    Pick a location with enough disk space — this is where Magellon will read inputs, write outputs, and stage jobs.

    ```bash
    mkdir -p /path/to/magellon
    ```

6. ### Run the start script

    From the `Docker/` subdirectory, pass the processing directory and CUDA version:

    ```bash
    cd Docker
    bash start.sh /path/to/magellon <cuda-version>
    ```

    The first run downloads every supporting container; this can take a while on slow networks. When it finishes, several services come up — the Magellon front-end, the FastAPI backend, the Swagger interface, and a few internal helpers.

7. ### Move the demo data into GPFS

    Copy or move the Globus download into the `gpfs/` subdirectory of your processing directory:

    ```bash
    mv ~/Downloads/24dec03a /path/to/magellon/gpfs/
    ```

8. ### Import the session

    - Open the front-end at [http://localhost:8080/en/panel/images](http://localhost:8080/en/panel/images).
    - Log in, then open the menu (top-left).
    - Choose **Import**, switch to the **Magellon import** tab, and double-click `24dec03a` → `session.json`.
    - Click **IMPORT DATA**.

    <Aside type="note" title="Import time">
    Imports take 5–60 minutes depending on hardware. On Linux with a compatible GPU, frame alignment runs as part of the import and adds time.
    </Aside>

9. ### Explore

    Once the import finishes, browse the session in **Images**, run plugins from the **Plugins** page, and watch progress in the Jobs panel.

</Steps>

## Cleaning up

A teardown script ships alongside `start.sh`. **It deletes every Magellon subdirectory under the processing path** — only run it on a deployment you no longer need.

```bash
bash cleanup.sh /path/to/magellon
```
