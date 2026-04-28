"""Rebuild ``sample.mpn`` from ``sample_src/``.

Plain Python script (vs Makefile) so it works on Windows without bash
or make installed. Run from anywhere::

    python CoreService/tests/fixtures/plugins/build.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "sample_src"
OUT = HERE / "sample.mpn"


def main() -> int:
    if not SRC.is_dir():
        print(f"error: {SRC} not found", file=sys.stderr)
        return 1
    cmd = [
        sys.executable,
        "-m",
        "magellon_sdk.cli.main",
        "plugin",
        "pack",
        str(SRC),
        "-o",
        str(OUT),
        "--force",
    ]
    print("+", " ".join(cmd))
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        print(f"\nwrote {OUT}  ({OUT.stat().st_size:,} bytes)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
