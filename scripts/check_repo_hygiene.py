"""Fail when generated/runtime-only files are tracked by git."""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import PurePosixPath


FORBIDDEN_PATTERNS = (
    "*.pyc",
    "*.pyo",
    "*.log",
    ".env",
    "*/.env",
    "*/__pycache__/*",
    "*/node_modules/*",
    "*/venv/*",
    "*/.venv/*",
    "*/dist/*",
    "*/build/*",
    "*/.pytest_cache/*",
    "*/.ruff_cache/*",
    "*/playwright-report/*",
    "*/test-results/*",
)


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _is_forbidden(path: str) -> bool:
    normalized = PurePosixPath(path).as_posix()
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in FORBIDDEN_PATTERNS)


def main() -> int:
    offenders = [path for path in _tracked_files() if _is_forbidden(path)]
    if offenders:
        print("Generated/runtime-only files are tracked by git:", file=sys.stderr)
        for path in offenders:
            print(f"  {path}", file=sys.stderr)
        return 1
    print("Repository hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
