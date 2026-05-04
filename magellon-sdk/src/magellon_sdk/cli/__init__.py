"""``magellon-sdk`` command-line interface (H3a).

Registered as the ``magellon-sdk`` console script. Entry points:

- ``magellon-sdk plugin init <name>`` — scaffold a new plugin archive
  directory with a ready-to-edit ``plugin.yaml`` + README.
- ``magellon-sdk plugin pack <dir>`` — validate ``plugin.yaml`` and
  zip the directory into a ``<plugin_id>-<version>.mpn`` archive.
- ``magellon-sdk plugin validate <archive_or_dir>`` — validate a
  manifest without producing an archive. Safe to run in CI.

Kept intentionally argparse-only (stdlib) to avoid pulling in click /
typer as runtime deps of every plugin that installs the SDK.
"""
from __future__ import annotations

from magellon_sdk.cli.main import main

__all__ = ["main"]
