# Magellon SDK

Stable, versioned SDK for building Magellon plugins.

## Status

`2.4.0` - active SDK contract for Magellon plugins. The package exposes
the plugin base class, broker runner, progress reporting, CloudEvents
envelope, executor contracts, bus bootstrap helpers, plugin manifests,
configuration resolution, plugin archive metadata, and category
contracts.

## Install (dev, path-based)

```bash
pip install -e ./magellon-sdk
```

## Contract

Plugins should depend on `magellon-sdk` and avoid imports from
CoreService internals. Public compatibility expectations are documented
in `CONTRACT.md`.
