---
title: Container Management
description: Start, stop, inspect, and tear down the Magellon containers.
---

## Starting

On first run use the helper script, which also creates the required directories:

```bash
bash start.sh
```

For subsequent starts the compose command is enough:

```bash
docker compose --profile default up -d
```

## Inspecting

```bash
docker compose ps
docker compose logs -f core-service
```

## Stopping and cleaning up

```bash
docker compose --profile default down
```

Add `-v` to also drop volumes — safe in development, destructive in production.

## Common gotchas

- **Ports in use** — the stack binds 8080 (UI) and the core-service port. Stop conflicting services or remap in `.env`.
- **Permissions on GPFS** — if the container can't read imported data, check that the host's `MAGELLON_GPFS_PATH` is owned/readable by the compose user.
- **GPU access** — requires the NVIDIA container toolkit on the host.
