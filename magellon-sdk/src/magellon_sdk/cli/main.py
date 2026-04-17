"""``magellon-sdk`` dispatcher.

H3a subcommands:

- ``plugin init <name>``     — scaffold a new plugin archive directory.
- ``plugin pack <dir>``      — validate plugin.yaml and zip to .magplugin.
- ``plugin validate <path>`` — validate a manifest, file or zip.

Other subcommand groups (eg. ``hub login``, ``hub publish``) will
arrive with H3c.
"""
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path
from typing import List, Optional

from magellon_sdk import __version__
from magellon_sdk.archive.manifest import (
    CURRENT_SCHEMA_VERSION,
    PluginArchiveManifest,
    check_sdk_compat,
    load_manifest_bytes,
)


MANIFEST_FILENAME = "plugin.yaml"


TEMPLATE_MANIFEST = """\
schema_version: {schema}
plugin_id: {plugin_id}
name: {name}
version: 0.1.0
category: fft           # one of: fft, ctf, motioncor, pp, ...
sdk_compat: ">={sdk_major}.0,<{next_major}.0"
image:
  ref: ghcr.io/you/{plugin_id}:0.1.0
install_defaults:
  env: {{}}
  volumes:
    - host: /gpfs
      container: /gpfs
    - host: /jobs
      container: /jobs
  network: magellon_default
description: One-line description of what this plugin does.
developer: Your Name <you@example.com>
license: MIT
"""

TEMPLATE_README = """\
# {name}

(Describe what the plugin does and how to use it here.)

## Build + publish

1. Build the image: `docker build -t ghcr.io/you/{plugin_id}:0.1.0 .`
2. Push to a registry CoreService can pull from.
3. Pack this directory: `magellon-sdk plugin pack .`
4. Install via CoreService `/plugins/install/archive` (or the Install
   plugin UI -> "From archive" option).
"""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def cmd_plugin_init(args: argparse.Namespace) -> int:
    target = Path(args.name)
    if target.exists():
        sys.stderr.write(f"error: {target} already exists — refusing to overwrite\n")
        return 1
    target.mkdir(parents=True)
    plugin_id = target.name.lower().replace(" ", "-").replace("_", "-")
    sdk_major = int(__version__.split(".")[0])
    manifest = TEMPLATE_MANIFEST.format(
        schema=CURRENT_SCHEMA_VERSION,
        plugin_id=plugin_id,
        name=target.name,
        sdk_major=sdk_major,
        next_major=sdk_major + 1,
    )
    (target / MANIFEST_FILENAME).write_text(manifest, encoding="utf-8")
    (target / "README.md").write_text(
        TEMPLATE_README.format(name=target.name, plugin_id=plugin_id),
        encoding="utf-8",
    )
    sys.stdout.write(f"Scaffolded {target}/ with {MANIFEST_FILENAME} + README.md\n")
    sys.stdout.write(f"  plugin_id = {plugin_id}\n")
    sys.stdout.write(
        f"Next: edit {target}/{MANIFEST_FILENAME}, then "
        f"`magellon-sdk plugin pack {target}`\n"
    )
    return 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def _load_manifest_from_path(path: Path) -> PluginArchiveManifest:
    """Accept a directory, a ``plugin.yaml`` file, or a ``.magplugin`` zip."""
    if path.is_dir():
        manifest_path = path / MANIFEST_FILENAME
        if not manifest_path.exists():
            raise FileNotFoundError(
                f"{path} doesn't contain {MANIFEST_FILENAME} — "
                f"did you mean `magellon-sdk plugin init`?"
            )
        return load_manifest_bytes(manifest_path.read_bytes())
    if path.suffix in (".zip", ".magplugin"):
        with zipfile.ZipFile(path) as z:
            try:
                with z.open(MANIFEST_FILENAME) as f:
                    return load_manifest_bytes(f.read())
            except KeyError:
                raise FileNotFoundError(
                    f"{path} is a zip but has no top-level {MANIFEST_FILENAME} — "
                    f"pack it with `magellon-sdk plugin pack <dir>`"
                )
    if path.is_file():
        return load_manifest_bytes(path.read_bytes())
    raise FileNotFoundError(f"not found: {path}")


def cmd_plugin_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    try:
        manifest = _load_manifest_from_path(path)
    except Exception as exc:  # noqa: BLE001 — surface anything to the CLI user
        sys.stderr.write(f"invalid: {exc}\n")
        return 1

    try:
        check_sdk_compat(manifest.sdk_compat, __version__)
    except Exception as exc:  # noqa: BLE001
        # Compat is a warning at `validate` time — the plugin author
        # may be declaring the pin for a different deployment than
        # the one running this CLI. `install` enforces it hard.
        sys.stdout.write(
            f"OK with warning: {manifest.plugin_id} v{manifest.version} "
            f"(category={manifest.category}) — "
            f"sdk_compat {manifest.sdk_compat!r} vs CLI SDK {__version__}: {exc}\n"
        )
        return 0

    sys.stdout.write(
        f"OK: {manifest.plugin_id} v{manifest.version} "
        f"(category={manifest.category}, image={manifest.image.ref})\n"
    )
    return 0


# ---------------------------------------------------------------------------
# pack
# ---------------------------------------------------------------------------

def cmd_plugin_pack(args: argparse.Namespace) -> int:
    src = Path(args.dir)
    if not src.is_dir():
        sys.stderr.write(f"error: {src} is not a directory\n")
        return 1
    try:
        manifest = _load_manifest_from_path(src)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"error: {exc}\n")
        return 1

    out = Path(args.output or f"{manifest.plugin_id}-{manifest.version}.magplugin")
    if out.exists() and not args.force:
        sys.stderr.write(f"error: {out} already exists (pass --force to overwrite)\n")
        return 1

    # Pack plugin.yaml + README.md + any other non-hidden files under src.
    # Hidden files and __pycache__ are skipped — plugins don't need them
    # in the archive and they'd just bloat review.
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(src):
            # Drop hidden dirs + caches in-place so os.walk doesn't descend
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            for name in files:
                if name.startswith("."):
                    continue
                full = Path(root) / name
                arcname = full.relative_to(src).as_posix()
                z.write(full, arcname=arcname)

    sys.stdout.write(
        f"Packed {manifest.plugin_id} v{manifest.version} -> {out}\n"
    )
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magellon-sdk",
        description="Magellon Plugin SDK — author tooling.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"magellon-sdk {__version__}",
    )

    sub = parser.add_subparsers(dest="group", required=True, metavar="GROUP")

    # plugin group
    plugin = sub.add_parser("plugin", help="Plugin archive author tooling.")
    plugin_sub = plugin.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p_init = plugin_sub.add_parser(
        "init", help="Scaffold a new plugin archive directory."
    )
    p_init.add_argument("name", help="Directory to create for the new plugin.")
    p_init.set_defaults(func=cmd_plugin_init)

    p_pack = plugin_sub.add_parser(
        "pack", help="Validate plugin.yaml and zip the directory to .magplugin."
    )
    p_pack.add_argument("dir", help="Plugin directory containing plugin.yaml.")
    p_pack.add_argument(
        "-o", "--output",
        help="Output archive path. Defaults to <plugin_id>-<version>.magplugin.",
    )
    p_pack.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing output archive.",
    )
    p_pack.set_defaults(func=cmd_plugin_pack)

    p_val = plugin_sub.add_parser(
        "validate",
        help="Validate a plugin manifest (accepts a dir, a plugin.yaml, or a .magplugin zip).",
    )
    p_val.add_argument("path")
    p_val.set_defaults(func=cmd_plugin_validate)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
