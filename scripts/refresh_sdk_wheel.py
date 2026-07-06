"""Keep the SDK wheels bundled in plugin directories in sync.

Plugins vendor a ``magellon_sdk-<version>-py3-none-any.whl`` (in
``wheels/`` or the plugin root) that their Dockerfiles install. When
the SDK version bumps without refreshing these, plugin image builds
break at import time (`ImportError: cannot import name ...`) — a
failure mode this repo has hit before.

Usage:
    python scripts/refresh_sdk_wheel.py --check   # CI gate: versions match?
    python scripts/refresh_sdk_wheel.py           # build + replace wheels
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SDK = REPO / "magellon-sdk"
PLUGINS = REPO / "plugins"
WHEEL_RE = re.compile(r"^magellon_sdk-(?P<version>[^-]+)-py3-none-any\.whl$")


def sdk_version() -> str:
    text = (SDK / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "(?P<v>[^"]+)"', text, flags=re.M)
    assert match, "version not found in magellon-sdk/pyproject.toml"
    return match.group("v")


def bundled_wheels() -> list[Path]:
    """Tracked bundled wheels only — skip .venv site-packages copies."""
    hits = []
    for path in PLUGINS.rglob("magellon_sdk-*-py3-none-any.whl"):
        if ".venv" in path.parts or "site-packages" in path.parts:
            continue
        hits.append(path)
    return sorted(hits)


# Files that name the wheel with an explicit version (Dockerfile COPY
# lines, requirements entries). Globs are relative to plugins/.
REFERENCE_GLOBS = (
    "*/Dockerfile",
    "*/Dockerfile.test",
    "*/requirements*.txt",
)
REFERENCE_RE = re.compile(r"magellon_sdk-(?P<version>[0-9][^-\s]*)-py3-none-any\.whl")


def _reference_files() -> list[Path]:
    hits: list[Path] = []
    for pattern in REFERENCE_GLOBS:
        hits.extend(PLUGINS.glob(pattern))
    return sorted(p for p in hits if p.is_file())


def check() -> int:
    version = sdk_version()
    stale = []
    for wheel in bundled_wheels():
        match = WHEEL_RE.match(wheel.name)
        if not match or match.group("version") != version:
            stale.append(f"{wheel.relative_to(REPO)} (SDK is {version})")
    for ref in _reference_files():
        text = ref.read_text(encoding="utf-8")
        for match in REFERENCE_RE.finditer(text):
            if match.group("version") != version:
                stale.append(
                    f"{ref.relative_to(REPO)} references {match.group(0)} (SDK is {version})"
                )
    if stale:
        print("Stale bundled SDK wheels — run scripts/refresh_sdk_wheel.py:", file=sys.stderr)
        for line in stale:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"All bundled SDK wheels and references match {version}")
    return 0


def refresh() -> int:
    version = sdk_version()
    dist = SDK / "dist"
    fresh = dist / f"magellon_sdk-{version}-py3-none-any.whl"
    if not fresh.exists():
        print(f"Building magellon_sdk {version} wheel ...")
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
            cwd=SDK, check=True,
        )
    assert fresh.exists(), f"expected {fresh} after build"

    for wheel in bundled_wheels():
        target = wheel.parent / fresh.name
        if wheel.name != fresh.name:
            print(f"replacing {wheel.relative_to(REPO)} -> {fresh.name}")
            wheel.unlink()
        shutil.copy2(fresh, target)

    for ref in _reference_files():
        text = ref.read_text(encoding="utf-8")
        updated = REFERENCE_RE.sub(fresh.name, text)
        if updated != text:
            print(f"rewriting wheel reference in {ref.relative_to(REPO)}")
            ref.write_text(updated, encoding="utf-8")
    return check()


def main() -> int:
    if "--check" in sys.argv[1:]:
        return check()
    return refresh()


if __name__ == "__main__":
    raise SystemExit(main())
