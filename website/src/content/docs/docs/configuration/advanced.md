---
title: Advanced Configuration
description: Knobs for larger deployments and custom topologies.
---

The defaults work for a single workstation. A few knobs matter once you move beyond that.

## External databases

The core service talks to MySQL via SQLAlchemy. To point at an existing instance instead of the bundled container, override the database URL in `.env` and stop the `mysql` service in your compose profile.

## Alembic migrations

Schema changes ship as Alembic migrations in `CoreService/alembic/`. On container start the service applies pending migrations automatically; for controlled deploys, run them manually with `alembic upgrade head` before bringing up the app container.

## Plugin discovery

Plugins are discovered at service start by walking `CoreService/plugins/<category>/<name>/service.py`. Adding a plugin means dropping a package — no central registration. Missing external binaries surface through each plugin's `check_requirements` output.

## GPU allocation

The MotionCor2 plugin exposes `gpu_ids` directly; for ctffind and picking plugins, use `CUDA_VISIBLE_DEVICES` on the worker container.
