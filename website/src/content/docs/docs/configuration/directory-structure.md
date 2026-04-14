---
title: Directory Structure
description: How Magellon lays out data, jobs, and services on disk.
---

Magellon expects three top-level data directories plus a services directory.

```
magellon/
├── home/       # Generated files
├── gpfs/       # Data imports (mounted as /gpfs inside containers)
├── jobs/       # Temporary job storage
└── services/   # Service-specific working state
```

Paths are passed into the containers via environment variables — see [Environment Settings](/docs/configuration/environment/). Keeping these directories on fast storage (SSD, local GPFS) has a measurable impact on import time and job throughput.
