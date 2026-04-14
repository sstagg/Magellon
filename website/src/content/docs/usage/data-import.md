---
title: Data Import
description: Bring a session into Magellon.
---

import { Steps } from '@astrojs/starlight/components';

<Steps>

1. Drop (or symlink) your session directory into the configured GPFS path — e.g. `/magellon/gpfs/<your-session>/`.

2. Open the UI at [http://localhost:8080](http://localhost:8080) and log in.

3. Click the menu icon and choose **Import**.

4. In the **Magellon import** tab, navigate to your session directory and double-click its `session.json`.

5. Click **IMPORT DATA**.

</Steps>

Import can take 5–60 minutes depending on dataset size and whether frame alignment is running on a GPU. Progress streams into the Jobs panel — leave the tab open or check back later; the state persists.
