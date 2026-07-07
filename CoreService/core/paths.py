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
