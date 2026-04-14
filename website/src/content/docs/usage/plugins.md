---
title: Plugins
description: How to run plugins and extend the platform with your own.
---

The **Plugins** page lists every discovered plugin with its category and version. Clicking one opens the runner, which:

1. Fetches the plugin's JSON input schema.
2. Renders a form (enum → select, boolean → checkbox, number → numeric field, etc.) with sensible defaults.
3. Submits the job and subscribes to progress via Socket.IO.
4. On completion, renders a plugin-specific result view when one is registered, or falls back to a JSON view.

## Batch submission

Most plugins accept batch submission — one job per image, sharing a common parameter set. The jobs panel groups them by submission so progress is easy to track.

## Writing a plugin

A minimal plugin package looks like this:

```
CoreService/plugins/<category>/<name>/
├── __init__.py
├── service.py      # subclass of PluginBase
└── models.py       # Pydantic input/output schemas
```

The framework handles discovery, schema exposure, job persistence, and progress streaming. A plugin's job is to:

- Declare its inputs and outputs (Pydantic).
- Advertise external dependencies (`check_requirements`).
- Implement `execute`, yielding progress as it runs.

For a plugin-specific front-end renderer, register a React component in the plugin-runner's renderer registry keyed by `plugin_id`. Without a custom renderer, results fall back to a readable JSON view — useful for internal tooling and early prototypes.
