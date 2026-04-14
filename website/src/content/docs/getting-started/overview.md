---
title: Overview
description: What Magellon is and how its pieces fit together.
---

Magellon is a cryo-EM workflow platform. It ties together a FastAPI core service, a React front-end, and a growing library of processing plugins (CTF estimation, motion correction, particle picking) behind a shared job model.

## Architecture at a glance

- **Core service** — FastAPI + SQLAlchemy. Owns the plugin registry, job persistence, and Socket.IO progress streaming.
- **Plugins** — Python packages under `CoreService/plugins/<category>/<name>`. Each exposes Pydantic input/output schemas and a lifecycle the framework drives.
- **Front-end** — React 19 + MUI 7. The plugin runner generates forms from each plugin's JSON Schema, so adding a plugin does not require UI work.
- **Persistence** — MySQL (via Alembic migrations). Jobs and their settings are stored as JSON columns so schema evolution stays cheap.
- **Transport** — REST for control, Socket.IO for live progress.

## Where to go next

- [Installation](/getting-started/installation/) — Docker-based setup.
- [Quick Start](/getting-started/quick-start/) — run your first job end-to-end.
- [Plugins](/usage/plugins/) — understand the runner and extend it.
