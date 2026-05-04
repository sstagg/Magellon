"""Plugin port allocation (R2 #4, 2026-05-04).

When a plugin advertises ``Capability.SYNC`` or ``Capability.PREVIEW``
its FastAPI host needs a port CoreService can reach. The install
pipeline assigns one at install time and persists it so:

  - The plugin's ``runtime.env`` can carry
    ``MAGELLON_PLUGIN_HTTP_ENDPOINT=http://127.0.0.1:<port>`` to
    the systemd unit / docker container.
  - The mapping survives CoreService restarts — the port stays
    pinned to the plugin until it's uninstalled.
  - Two plugins on the same host don't collide.

Port range defaults to 18000-18999 (1000 plugins ought to be enough
for any deployment); operators can override via the
``MAGELLON_PLUGIN_PORT_MIN`` / ``..._MAX`` env vars. Allocation
state lives in ``<plugins_dir>/.port_assignments.json`` so the
allocator is process-restart safe.

Allocation strategy:
  1. If the plugin already has an entry, return it (idempotent).
  2. Find a free port in [min, max] not in the persisted assignment
     map AND not currently bound on the loopback interface.
  3. Persist before returning so a crash mid-install doesn't strand
     a port.

Exhaustion is a hard error — no silent fallback (operator wants
to know they over-provisioned).
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Defaults — operators can override via env without redeploying
# ---------------------------------------------------------------------------


def _default_port_min() -> int:
    raw = os.environ.get("MAGELLON_PLUGIN_PORT_MIN")
    return int(raw) if raw else 18000


def _default_port_max() -> int:
    raw = os.environ.get("MAGELLON_PLUGIN_PORT_MAX")
    return int(raw) if raw else 18999


_STATE_FILENAME = ".port_assignments.json"
_global_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PortRangeExhausted(RuntimeError):
    """No free port in the configured [min, max] range."""


# ---------------------------------------------------------------------------
# Allocator
# ---------------------------------------------------------------------------


class PluginPortAllocator:
    """Per-plugins-dir port assignments, persisted to disk."""

    def __init__(
        self,
        plugins_dir: Path,
        *,
        port_min: Optional[int] = None,
        port_max: Optional[int] = None,
    ) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.port_min = port_min if port_min is not None else _default_port_min()
        self.port_max = port_max if port_max is not None else _default_port_max()
        if self.port_max < self.port_min:
            raise ValueError(
                f"port_max ({self.port_max}) must be >= port_min "
                f"({self.port_min})"
            )

    @property
    def state_path(self) -> Path:
        return self.plugins_dir / _STATE_FILENAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def allocate(self, plugin_id: str) -> int:
        """Return a port assigned to ``plugin_id``. Idempotent — same
        plugin gets the same port across calls."""
        with _global_lock:
            assignments = self._load()
            existing = assignments.get(plugin_id)
            if existing is not None:
                if self.port_min <= existing <= self.port_max:
                    return int(existing)
                logger.info(
                    "plugin %s had out-of-range port %s — re-allocating",
                    plugin_id, existing,
                )

            taken = {int(p) for p in assignments.values()
                     if self.port_min <= int(p) <= self.port_max}
            for port in range(self.port_min, self.port_max + 1):
                if port in taken:
                    continue
                if not _is_port_free(port):
                    continue
                assignments[plugin_id] = port
                self._save(assignments)
                return port

            raise PortRangeExhausted(
                f"no free port in [{self.port_min}, {self.port_max}] for "
                f"plugin {plugin_id!r}; bump MAGELLON_PLUGIN_PORT_MAX or "
                f"uninstall stale plugins",
            )

    def get(self, plugin_id: str) -> Optional[int]:
        """Return the assigned port without allocating a new one."""
        with _global_lock:
            assignments = self._load()
            value = assignments.get(plugin_id)
            return int(value) if value is not None else None

    def release(self, plugin_id: str) -> None:
        """Drop a plugin's port assignment. Safe if missing."""
        with _global_lock:
            assignments = self._load()
            if plugin_id in assignments:
                del assignments[plugin_id]
                self._save(assignments)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict[str, int]:
        if not self.state_path.exists():
            return {}
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            logger.exception("port_allocator: failed to read %s; starting fresh",
                             self.state_path)
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(k): int(v) for k, v in data.items() if isinstance(v, int)}

    def _save(self, assignments: Dict[str, int]) -> None:
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        # Write atomically — a crash mid-write shouldn't corrupt
        # the assignment map.
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(assignments, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp.replace(self.state_path)


def _is_port_free(port: int) -> bool:
    """Return True if the port is bindable on the loopback interface
    right now. Best-effort — there's an obvious race between probing
    and the plugin binding, but operator-visible collisions are
    typically rare in the [18000-18999] range."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False


__all__ = [
    "PluginPortAllocator",
    "PortRangeExhausted",
]
