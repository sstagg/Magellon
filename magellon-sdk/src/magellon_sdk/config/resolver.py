"""Layered plugin-config resolver (G.3).

A plugin today reads its config from four surfaces:

1. **Caller-supplied defaults** — hardcoded in the plugin class or
   ``CategoryContract`` (e.g. a default CTF max-resolution).
2. **Static YAML** — ``configs/settings_{dev,prod}.yml`` loaded at
   startup by :class:`BaseAppSettings`.
3. **Environment variables** — ``MAGELLON_STEP_EVENTS_ENABLED``,
   ``APP_ENV``, and per-plugin tunables; convenient for
   docker-compose overrides.
4. **Bus-pushed runtime config** — ``magellon.plugins.config.<category>``
   messages routed through :class:`ConfigSubscriber`; applied to the
   plugin between task deliveries via ``plugin.configure(...)``.

Each surface has its own read pattern in the plugin code today
(``settings.X``, ``os.environ.get(...)``, ``configure(dict)``, etc.),
which means a plugin author has to know all four. G.3 folds them into
one read path so the plugin asks ``resolver.get("max_resolution")``
and the resolver walks the precedence chain.

Precedence (highest wins):

  1. Runtime overrides (most recent bus push) — this is the operator
     saying "change now".
  2. Env vars — this is the deployment saying "here's the local
     override".
  3. YAML — this is the plugin's baked-in production config.
  4. Defaults — this is "what the plugin ships with".

Not in scope:

- **Hot-reload of YAML / env.** Processes re-read YAML only on
  restart; env is read once at resolver construction. Runtime changes
  go via the bus, which is how the config-broker was already designed.
- **Writing back.** Resolver is read-only. To push a new value, use
  :mod:`magellon_sdk.config_broker.ConfigPublisher`.
- **Type coercion magic.** We provide explicit ``get_bool`` /
  ``get_int`` / ``get_float`` / ``get_str`` accessors so callers are
  explicit about what they expect; ``get`` returns the raw value.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class PluginConfigResolver:
    """Layered read-only config lookup.

    Construct once at plugin startup with the static values
    (defaults + YAML); call :meth:`apply_overrides` each time the
    plugin's ``configure(...)`` is invoked by the runner with bus-
    pushed updates. Env vars are read at :meth:`get` time so a runtime
    ``os.environ[...] = ...`` (rare, but valid in tests) is honoured.

    Thread-safe: overrides protected by a lock so concurrent
    apply_overrides / get calls are safe. Per-lookup cost is two dict
    checks plus an os.environ lookup — cheap enough that plugins can
    call it inside hot loops.

    ``env_prefix`` defaults to ``MAGELLON_`` to match the convention
    used by existing env-var overrides in plugin ``main.py`` files.
    The env var for a key ``max_resolution`` is ``MAGELLON_MAX_RESOLUTION``
    (upper-cased, with the prefix). Plugins that need a different
    prefix (e.g. a CTF-specific namespace) pass one explicitly.
    """

    _UNSET = object()

    def __init__(
        self,
        *,
        defaults: Optional[Dict[str, Any]] = None,
        yaml_values: Optional[Dict[str, Any]] = None,
        env_prefix: str = "MAGELLON_",
    ) -> None:
        self._defaults: Dict[str, Any] = dict(defaults or {})
        self._yaml: Dict[str, Any] = dict(yaml_values or {})
        self._env_prefix = env_prefix
        self._overrides: Dict[str, Any] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Writes (overrides layer only)
    # ------------------------------------------------------------------

    def apply_overrides(self, values: Dict[str, Any]) -> None:
        """Merge runtime updates from the bus-pushed config subscriber.

        Last-write-wins per key — same semantics as
        :meth:`ConfigSubscriber.take_pending` returning merged state.
        Keys that were previously overridden but are absent from
        ``values`` stay as-is; this is *merge*, not *replace*.
        """
        if not values:
            return
        with self._lock:
            self._overrides.update(values)
        logger.info(
            "PluginConfigResolver: applied %d override(s): %s",
            len(values), sorted(values.keys()),
        )

    def clear_overrides(self) -> None:
        """Drop every runtime override. Mostly useful for tests +
        emergency rollback."""
        with self._lock:
            self._overrides.clear()

    # ------------------------------------------------------------------
    # Reads (layered)
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the highest-precedence value for ``key``.

        Precedence: runtime overrides → env var → YAML → caller
        defaults (constructor-supplied) → ``default`` argument.
        """
        with self._lock:
            if key in self._overrides:
                return self._overrides[key]

        env_val = self._env_lookup(key)
        if env_val is not self._UNSET:
            return env_val

        if key in self._yaml:
            return self._yaml[key]
        if key in self._defaults:
            return self._defaults[key]
        return default

    def _env_lookup(self, key: str) -> Any:
        env_key = f"{self._env_prefix}{key.upper()}"
        val = os.environ.get(env_key, self._UNSET)
        return val

    def get_bool(self, key: str, default: bool = False) -> bool:
        raw = self.get(key, None)
        if raw is None:
            return default
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")

    def get_int(self, key: str, default: int = 0) -> int:
        raw = self.get(key, None)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            logger.warning(
                "PluginConfigResolver: key %s has non-integer value %r — "
                "returning default %d", key, raw, default,
            )
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        raw = self.get(key, None)
        if raw is None:
            return default
        try:
            return float(raw)
        except (TypeError, ValueError):
            logger.warning(
                "PluginConfigResolver: key %s has non-numeric value %r — "
                "returning default %f", key, raw, default,
            )
            return default

    def get_str(self, key: str, default: str = "") -> str:
        raw = self.get(key, None)
        if raw is None:
            return default
        return str(raw)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Merged view of every layer — for logging / diagnostics.

        Env vars under the prefix are eagerly enumerated here (even
        though they're otherwise looked up lazily) so a snapshot is a
        self-contained record of effective config at the moment of
        capture. Overrides win, then env, then YAML, then defaults.
        """
        merged: Dict[str, Any] = dict(self._defaults)
        merged.update(self._yaml)
        for env_key, env_val in os.environ.items():
            if env_key.startswith(self._env_prefix):
                # Strip prefix + lowercase so the snapshot uses the
                # same key form the caller passes to get().
                merged[env_key[len(self._env_prefix):].lower()] = env_val
        with self._lock:
            merged.update(self._overrides)
        return merged


__all__ = ["PluginConfigResolver"]
