---
title: Quick Start
description: The shortest path from a fresh checkout to a running job.
---

import { Steps } from '@astrojs/starlight/components';

<Steps>

1. Clone and enter the repo.

    ```bash
    git clone https://github.com/sstagg/Magellon.git
    cd Magellon/Docker
    ```

2. Copy the example config and start the stack.

    ```bash
    cp .env.example .env
    bash start.sh
    ```

3. Open the UI at [http://localhost:8080](http://localhost:8080) and log in.

4. Import a session, open the **Plugins** page, pick a plugin, fill the generated form, and click **Run**.

</Steps>

For a fuller walk-through — including demo data — see [Installation](/getting-started/installation/).
