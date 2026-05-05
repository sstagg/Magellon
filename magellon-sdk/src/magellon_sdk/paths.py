"""Path translation helpers for plugin-side code.

Wire paths between CoreService and plugins are always canonical
``/gpfs/...`` (see ``Documentation/DATA_PLANE.md``). Plugins still need
to open files locally, and "locally" depends on the deployment:

* **Docker container** — bind-mounts the host's GPFS at ``/gpfs``,
  so canonical paths just work. ``MAGELLON_GPFS_PATH`` defaults to
  ``/gpfs``; the helpers below are no-ops.
* **uv install on Linux** — same ``/gpfs`` story; no-op.
* **uv install on Windows** — runtime.env sets
  ``MAGELLON_GPFS_PATH=C:/magellon/gpfs`` (or wherever the host
  actually has it). The helpers rewrite ``/gpfs/foo.mrc`` →
  ``C:/magellon/gpfs/foo.mrc`` so :func:`open` / :func:`mrcfile.open`
  hit a real file.

Plugin authors typically only need :func:`from_canonical_gpfs_path`
and pair it with their own ``open()`` calls. There is no central
filesystem layer in the SDK — keeping the rewrite at the I/O
boundary keeps the helpers small, predictable, and testable in
isolation.

CoreService has its own copy of these helpers in ``core/helper.py``
because the SDK isn't a dependency there; both sides must stay in
sync. The shapes match — anything that round-trips through one
should round-trip through the other.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path, None]


def from_canonical_gpfs_path(
    path: PathLike, *, gpfs_path: Optional[str] = None,
) -> Optional[str]:
    """Translate a canonical ``/gpfs/...`` path to the plugin's
    local-filesystem form.

    ``gpfs_path`` is the plugin's view of the GPFS root; defaults to
    ``MAGELLON_GPFS_PATH`` from the SDK's settings (which itself
    defaults to ``/gpfs``, the canonical no-op).

    Examples (with ``gpfs_path='C:/magellon/gpfs'``)::

        from_canonical_gpfs_path('/gpfs/foo.mrc')
            -> 'C:/magellon/gpfs/foo.mrc'
        from_canonical_gpfs_path('/gpfs')
            -> 'C:/magellon/gpfs'

    With ``gpfs_path='/gpfs'`` or omitted on a default Linux install,
    inputs pass through unchanged. Falsy / non-canonical inputs
    (anything that doesn't start with ``/gpfs``) also pass through —
    callers can use this unconditionally without checking the input
    shape themselves.
    """
    if not path:
        return path  # type: ignore[return-value]
    norm = str(path).replace("\\", "/")
    root = (gpfs_path or _default_gpfs_path()).replace("\\", "/").rstrip("/")
    if not root or root == "/gpfs":
        return norm
    if norm == "/gpfs":
        return root
    if norm.startswith("/gpfs/"):
        return root + "/" + norm[len("/gpfs/"):]
    return norm


def to_canonical_gpfs_path(
    path: PathLike, *, gpfs_path: Optional[str] = None,
) -> Optional[str]:
    """Inverse of :func:`from_canonical_gpfs_path` — collapse a
    plugin-local path back to its canonical ``/gpfs/...`` form.

    Symmetric to CoreService's ``core.helper.to_canonical_gpfs_path``.
    Used when a plugin needs to emit a path that flows back across the
    bus (e.g. into a TaskResultMessage); the receiver only ever
    handles canonical paths.
    """
    if not path:
        return path  # type: ignore[return-value]
    norm = str(path).replace("\\", "/")
    root = (gpfs_path or _default_gpfs_path()).replace("\\", "/").rstrip("/")
    if not root or root == "/gpfs":
        return norm
    # Case-insensitive prefix match — Windows paths come through as
    # ``C:/magellon/gpfs`` regardless of how the OS spells the drive.
    norm_lower = norm.lower()
    root_lower = root.lower()
    if norm_lower == root_lower:
        return "/gpfs"
    if norm_lower.startswith(root_lower + "/"):
        return "/gpfs/" + norm[len(root) + 1:]
    return norm


def _default_gpfs_path() -> str:
    """Pull ``MAGELLON_GPFS_PATH`` from SDK settings if available, else
    fall back to ``/gpfs``. Wrapped in a function so import-time
    ordering doesn't pin a stale value before the plugin's settings
    YAML loads."""
    try:
        from magellon_sdk.config.settings import BaseAppSettings
        # BaseAppSettings is the schema; plugins extend it. The class-level
        # default reflects ``/gpfs`` on Linux/Docker. Plugins that override
        # via runtime.env / settings YAML pass ``gpfs_path=`` explicitly.
        default = BaseAppSettings.model_fields.get("MAGELLON_GPFS_PATH")
        if default is not None and default.default:
            return str(default.default)
    except Exception:  # noqa: BLE001 — keep helpers usable in isolation
        pass
    return "/gpfs"


__all__ = ["from_canonical_gpfs_path", "to_canonical_gpfs_path"]
