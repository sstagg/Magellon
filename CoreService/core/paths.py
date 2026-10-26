"""Path canonicalization across the CoreService/plugin wire boundary.

Wire paths between CoreService and plugins are always canonical
``/gpfs/...`` (see ``Documentation/DATA_PLANE.md``). These helpers
translate between that canonical form and the host-absolute form this
CoreService process uses for direct filesystem access.

Split out of ``core.helper`` (2026-07-06); import from here in new code,
``core.helper`` re-exports for existing call sites.
"""
from config import app_settings


def to_canonical_gpfs_path(path):
    """Translate a host-absolute path under MAGELLON_GPFS_PATH to its
    canonical ``/gpfs/...`` form for transport across realms (bus payloads,
    plugin task DTOs).

    The hybrid Windows-host + Docker-plugin topology has different paths
    on each side of the bus: CoreService sees ``C:/magellon/gpfs/...``,
    the plugin container sees ``/gpfs/...`` (single bind mount). Wire
    paths are always canonical ``/gpfs/...`` and each side resolves them
    locally (the ``/web/files/browse`` endpoint does the inverse rewrite
    on inbound paths). On Linux deployments where MAGELLON_GPFS_PATH is
    already ``/gpfs`` this is a no-op; ``None`` and falsy paths pass
    through.

    Thin wrapper over :func:`magellon_sdk.paths.to_canonical_gpfs_path`
    so the SDK and CoreService halves of the path-translation contract
    stay symmetric automatically.
    """
    if not path:
        return path
    from magellon_sdk.paths import to_canonical_gpfs_path as _sdk_to
    return _sdk_to(
        path, gpfs_path=app_settings.directory_settings.MAGELLON_GPFS_PATH,
    )


def from_canonical_gpfs_path(path):
    """Inverse of :func:`to_canonical_gpfs_path` — translate a canonical
    ``/gpfs/...`` path to the host-absolute path appropriate for direct
    filesystem access on this CoreService process.

    On Linux deployments where ``MAGELLON_GPFS_PATH=/gpfs`` this is a
    no-op; on Windows direct-run with ``C:/magellon/gpfs`` it rewrites
    ``/gpfs/sessions/foo.mrc`` → ``C:/magellon/gpfs/sessions/foo.mrc``.

    Falsy / non-canonical inputs pass through unchanged. Callers must
    still validate the result is under the GPFS root before using it
    for I/O — see :func:`is_under_gpfs_root`.

    Thin wrapper over :func:`magellon_sdk.paths.from_canonical_gpfs_path`.
    """
    if not path:
        return path
    from magellon_sdk.paths import from_canonical_gpfs_path as _sdk_from
    return _sdk_from(
        path, gpfs_path=app_settings.directory_settings.MAGELLON_GPFS_PATH,
    )


def canonicalize_paths_in_payload(value):
    """Recursively walk a JSON-like payload, applying
    :func:`to_canonical_gpfs_path` to every string value.

    The bus dispatcher canonicalizes paths at every wire boundary
    (``core.helper.dispatch_*`` callsites). The sync HTTP path
    (``services.sync_dispatcher``) used to forward bodies verbatim —
    a Windows React client posting ``{"image_path": "C:/magellon/gpfs/..."}``
    reached a Docker plugin that couldn't open the path. This walker
    closes that gap: any string that lies under the configured
    ``MAGELLON_GPFS_PATH`` is rewritten to canonical ``/gpfs/...``;
    everything else passes through.

    Safe to apply unconditionally — :func:`to_canonical_gpfs_path` is
    a no-op on Linux (``MAGELLON_GPFS_PATH=/gpfs``) and on any string
    not under the configured root.
    """
    if isinstance(value, str):
        return to_canonical_gpfs_path(value)
    if isinstance(value, dict):
        return {k: canonicalize_paths_in_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [canonicalize_paths_in_payload(v) for v in value]
    if isinstance(value, tuple):
        return tuple(canonicalize_paths_in_payload(v) for v in value)
    return value


def is_under_gpfs_root(host_path):
    """Defense-in-depth: confirm a host-resolved path lies under the
    configured GPFS root. Catches symlink escapes / odd traversal that
    string-prefix checks miss, since :class:`pathlib.Path.resolve`
    walks symlinks.

    Returns ``True`` when ``host_path`` is the GPFS root or a descendant.
    Returns ``False`` when the GPFS root isn't configured (refuse rather
    than fall open).
    """
    from pathlib import Path
    gpfs = app_settings.directory_settings.MAGELLON_GPFS_PATH
    if not gpfs:
        return False
    try:
        gpfs_root = Path(gpfs).resolve()
        target = Path(host_path).resolve()
        target.relative_to(gpfs_root)
        return True
    except (ValueError, OSError):
        return False


# ---------------------------------------------------------------------------
# Magellon's own storage (MAGELLON_HOME_DIR, wire form ``/magellon/...``).
#
# /gpfs (the research data tree) is read-only for Magellon; anything users
# add — uploaded templates, uploaded files — goes under MAGELLON_HOME_DIR
# instead. Only these subfolders are browsable/uploadable: the rest of it
# holds every user's per-session results, which the session access checks
# protect, so the file browser must not list it.
# ---------------------------------------------------------------------------
MAGELLON_WIRE_ROOT = "/magellon"
MAGELLON_SHARED_DIRS = ("uploads", "templates")


def is_magellon_wire_path(path) -> bool:
    """True for ``/magellon`` or anything below it."""
    norm = (path or "").replace("\\", "/")
    return norm == MAGELLON_WIRE_ROOT or norm.startswith(MAGELLON_WIRE_ROOT + "/")


def resolve_magellon_shared_path(path):
    """Map a ``/magellon/...`` wire path to its real location.

    Returns the Magellon root itself for ``/magellon`` (callers list only
    the shared folders there), or a path inside one of
    :data:`MAGELLON_SHARED_DIRS`. Raises ``ValueError`` for anything else,
    including ``..``/symlink escapes. The shared folders are created on
    first use.
    """
    from pathlib import Path
    from config import MAGELLON_HOME_DIR

    if not is_magellon_wire_path(path):
        raise ValueError(f"{path!r} is not a {MAGELLON_WIRE_ROOT} path")
    root = Path(MAGELLON_HOME_DIR).resolve()
    for name in MAGELLON_SHARED_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)

    relative = path.replace("\\", "/")[len(MAGELLON_WIRE_ROOT):].strip("/")
    if not relative:
        return root
    target = (root / relative).resolve()
    for name in MAGELLON_SHARED_DIRS:
        base = (root / name).resolve()
        if target == base or base in target.parents:
            return target
    raise ValueError(
        f"{path!r} is outside the shared Magellon folders "
        f"({', '.join(MAGELLON_WIRE_ROOT + '/' + n for n in MAGELLON_SHARED_DIRS)})"
    )


def to_magellon_wire_path(real_path) -> str:
    """Inverse of :func:`resolve_magellon_shared_path`."""
    from pathlib import Path
    from config import MAGELLON_HOME_DIR

    relative = Path(real_path).resolve().relative_to(Path(MAGELLON_HOME_DIR).resolve())
    return MAGELLON_WIRE_ROOT + ("/" + relative.as_posix() if str(relative) != "." else "")
