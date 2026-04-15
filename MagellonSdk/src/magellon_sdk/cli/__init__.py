"""magellon-plugin command-line interface.

Entry point declared in pyproject.toml as ``magellon-plugin``. Subcommands
stubbed at 0.1.0 — implementations arrive in later PRs (new, test,
package, publish). Using the stdlib ``argparse`` to keep the SDK
dependency-light (no click on the plugin author's critical path).
"""
from __future__ import annotations

from magellon_sdk.cli.main import main

__all__ = ["main"]
