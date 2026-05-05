"""Tests for ``magellon_sdk.paths`` — the GPFS canonical/local
path-translation helpers plugins use at I/O boundaries."""
from __future__ import annotations

from magellon_sdk.paths import (
    from_canonical_gpfs_path,
    to_canonical_gpfs_path,
)


# ---------------------------------------------------------------------------
# Linux / Docker — gpfs root is /gpfs, helpers are no-ops
# ---------------------------------------------------------------------------


def test_from_canonical_noop_when_root_is_gpfs():
    """In a Docker container the bind mount IS at /gpfs, so the
    canonical path opens directly. Helper should return it unchanged."""
    assert from_canonical_gpfs_path("/gpfs/sessions/x.mrc", gpfs_path="/gpfs") \
        == "/gpfs/sessions/x.mrc"


def test_to_canonical_noop_when_root_is_gpfs():
    assert to_canonical_gpfs_path("/gpfs/sessions/x.mrc", gpfs_path="/gpfs") \
        == "/gpfs/sessions/x.mrc"


# ---------------------------------------------------------------------------
# Windows direct-run — gpfs root is C:/magellon/gpfs
# ---------------------------------------------------------------------------


def test_from_canonical_rewrites_to_windows_root():
    """Plugin running uv direct on Windows opens the actual file via
    the Windows path; the wire path must be rewritten."""
    assert from_canonical_gpfs_path(
        "/gpfs/sessions/x.mrc", gpfs_path="C:/magellon/gpfs",
    ) == "C:/magellon/gpfs/sessions/x.mrc"


def test_from_canonical_handles_root_only():
    assert from_canonical_gpfs_path(
        "/gpfs", gpfs_path="C:/magellon/gpfs",
    ) == "C:/magellon/gpfs"


def test_to_canonical_strips_windows_prefix():
    assert to_canonical_gpfs_path(
        "C:/magellon/gpfs/sessions/x.mrc", gpfs_path="C:/magellon/gpfs",
    ) == "/gpfs/sessions/x.mrc"


def test_to_canonical_case_insensitive_drive_match():
    """Windows paths sometimes come through with different drive-letter
    casing (``c:`` vs ``C:``); the canonical match should be tolerant."""
    assert to_canonical_gpfs_path(
        "c:/MAGELLON/gpfs/sessions/x.mrc", gpfs_path="C:/magellon/gpfs",
    ) == "/gpfs/sessions/x.mrc"


def test_to_canonical_root_only():
    assert to_canonical_gpfs_path(
        "C:/magellon/gpfs", gpfs_path="C:/magellon/gpfs",
    ) == "/gpfs"


# ---------------------------------------------------------------------------
# Pass-through: anything not under the canonical root is left alone.
# Lets callers apply the helper unconditionally.
# ---------------------------------------------------------------------------


def test_from_canonical_passes_through_non_canonical_input():
    """Plugin receives a non-canonical path (legacy, manually entered)?
    Don't mangle it — return as-is so the open() / mrcfile call sees
    what the operator typed."""
    assert from_canonical_gpfs_path(
        "C:/some/other/place/x.mrc", gpfs_path="C:/magellon/gpfs",
    ) == "C:/some/other/place/x.mrc"


def test_from_canonical_passes_through_falsy_input():
    assert from_canonical_gpfs_path(None) is None
    assert from_canonical_gpfs_path("") == ""


def test_to_canonical_passes_through_unrelated_input():
    assert to_canonical_gpfs_path(
        "/etc/passwd", gpfs_path="C:/magellon/gpfs",
    ) == "/etc/passwd"


def test_backslash_normalization():
    """Windows callers sometimes hand us native backslash paths.
    Helpers normalize before matching."""
    assert to_canonical_gpfs_path(
        r"C:\magellon\gpfs\sessions\x.mrc", gpfs_path="C:/magellon/gpfs",
    ) == "/gpfs/sessions/x.mrc"


def test_pathlib_input_supported():
    """Accept both str and Path inputs — plugins doing
    ``Path(input_data.image_path)`` shouldn't have to coerce back."""
    from pathlib import Path
    p = Path("/gpfs/sessions/x.mrc")
    out = from_canonical_gpfs_path(p, gpfs_path="C:/magellon/gpfs")
    assert out == "C:/magellon/gpfs/sessions/x.mrc"
