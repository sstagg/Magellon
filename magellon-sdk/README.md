# Magellon SDK

Stable, versioned SDK for building Magellon plugins.

## Status

`0.1.0` — scaffold. The plugin contract (`PluginBase`,
`ProgressReporter`, CloudEvents envelope, executor protocols) is
actively being extracted from `CoreService/plugins/` as part of the
platform refactor (see `Documentation/IMPLEMENTATION_PLAN.md`, Phase 1).

## Install (dev, path-based)

```bash
pip install -e ./magellon-sdk
```

## Contract

Until PRs 1.2–1.5 land, plugins should continue to import from
`CoreService.plugins.base`. Those modules will begin re-exporting from
`magellon_sdk` as each piece moves, so migration is transparent.
