---
title: Docker Setup
description: Install Docker and bring up the Magellon stack.
---

import { Steps } from '@astrojs/starlight/components';

<Steps>

1. Install [Docker Desktop](https://docs.docker.com/desktop/) and verify with `docker --version`.

2. Clone the repo and enter the `Docker/` directory.

    ```bash
    git clone https://github.com/sstagg/Magellon.git
    cd Magellon/Docker
    ```

3. Copy and edit `.env` — see [Environment Settings](/configuration/environment/).

4. Start the stack.

    ```bash
    bash start.sh
    ```

    The first run pulls and initialises every container; subsequent starts use the cached images.

</Steps>
