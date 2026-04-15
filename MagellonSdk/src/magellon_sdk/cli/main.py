"""``magellon-plugin`` dispatcher.

Subcommand implementations are stubs that print "not yet implemented"
and exit non-zero. Later PRs replace each stub with real behaviour:

- 1.7 (this PR): skeleton
- 2.1: ``worker`` subcommand (boots a Temporal worker for one plugin)
- 6.2: ``publish`` subcommand (uploads a wheel to the Plugin Hub)
- 6.x: ``new``, ``test``, ``package``
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from magellon_sdk import __version__


def _stub(name: str) -> int:
    sys.stderr.write(
        f"magellon-plugin {name}: not yet implemented "
        f"(SDK {__version__}; see Documentation/IMPLEMENTATION_PLAN.md).\n"
    )
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magellon-plugin",
        description="Build, test, and publish Magellon plugins.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"magellon-plugin {__version__}",
    )

    sub = parser.add_subparsers(dest="command", required=False, metavar="COMMAND")

    sub.add_parser("new", help="Scaffold a new plugin project (stub).")
    sub.add_parser("test", help="Run the plugin's test suite (stub).")
    sub.add_parser("package", help="Build a plugin wheel (stub).")
    sub.add_parser("publish", help="Upload to the plugin hub (stub).")
    sub.add_parser("worker", help="Run a Temporal worker for this plugin (stub).")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    return _stub(args.command)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
