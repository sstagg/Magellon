"""``magellon-plugin`` dispatcher.

``worker`` is live as of Phase 2 PR 2.2. The remaining subcommands are
stubs that print "not yet implemented" and exit non-zero. Later PRs
replace each stub with real behaviour (new/test/package from Phase 6,
publish from PR 6.2).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List, Optional

from magellon_sdk import __version__


def _stub(name: str) -> int:
    sys.stderr.write(
        f"magellon-plugin {name}: not yet implemented "
        f"(SDK {__version__}; see Documentation/IMPLEMENTATION_PLAN.md).\n"
    )
    return 2


def _cmd_worker(args: argparse.Namespace) -> int:
    # Imports deferred: the 'temporal' extra only needs to be installed
    # for this subcommand. Other stubs must not fail with ImportError.
    from magellon_sdk.worker import plugin_task_queue, run_worker
    from magellon_sdk.worker.discovery import PluginNotFound, load_plugin

    try:
        plugin = load_plugin(args.plugin)
    except PluginNotFound as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    task_queue = args.task_queue or plugin_task_queue(plugin)
    sys.stderr.write(
        f"magellon-plugin worker: plugin={args.plugin} "
        f"target={args.target} namespace={args.namespace} queue={task_queue}\n"
    )
    asyncio.run(
        run_worker(
            plugin,
            target=args.target,
            namespace=args.namespace,
            task_queue=task_queue,
        )
    )
    return 0


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

    worker = sub.add_parser(
        "worker",
        help="Run a Temporal worker for a plugin.",
        description=(
            "Boot a Temporal worker that exposes PLUGIN's run() as an "
            "activity. PLUGIN is looked up via entry-point group "
            "'magellon.plugins' first, then as 'MODULE:CLASSNAME'."
        ),
    )
    worker.add_argument(
        "--plugin",
        required=True,
        help="Plugin id (entry-point name) or 'MODULE:CLASSNAME' path.",
    )
    worker.add_argument(
        "--target",
        default="localhost:7233",
        help="Temporal server address (default: localhost:7233).",
    )
    worker.add_argument(
        "--namespace",
        default="default",
        help="Temporal namespace (default: default).",
    )
    worker.add_argument(
        "--task-queue",
        default=None,
        help="Override the canonical task queue name.",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    if args.command == "worker":
        return _cmd_worker(args)
    return _stub(args.command)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
