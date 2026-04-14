---
title: Environment Settings
description: The .env variables that drive the Magellon stack.
---

Magellon is configured through a `.env` file in the `Docker/` directory. Start from the example and edit in place:

```bash
cp .env.example .env
```

## Core paths

```bash
MAGELLON_HOME_PATH=/magellon/home
MAGELLON_GPFS_PATH=/magellon/gpfs
MAGELLON_JOBS_PATH=/magellon/jobs
```

These map into each container at fixed mount points, so code inside the stack can assume `/gpfs`, `/jobs`, and the home directory without any per-deploy changes.

## Common overrides

- Database credentials — default to the bundled MySQL container; override only when pointing at an external database.
- Logging level — set per-service; quieter defaults ship in `.env.example`.
- GPU selection — the motion-correction plugin honours `CUDA_VISIBLE_DEVICES` if you need to pin specific GPUs.
