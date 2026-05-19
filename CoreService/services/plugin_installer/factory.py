"""Process-wide :class:`PluginInstallManager` factory (P7).

Lazy-constructs the manager from app settings so importing this
module doesn't require a broker / docker / disk to exist. The
factory is exposed via :func:`get_install_manager` for FastAPI
``Depends(...)`` injection — tests override the dependency without
touching globals.

``RuntimeConfig`` (broker URL, GPFS root) is built from the same
settings the rest of CoreService reads. Plugin authors don't see
this — the archive declared what the plugin needs (per
``PLUGIN_ARCHIVE_FORMAT.md`` §6); CoreService provides the values.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, Optional

from services.plugin_installer.docker_installer import DockerInstaller
from services.plugin_installer.lifecycle import DockerLifecycle, UvLifecycle
from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.protocol import RuntimeConfig
from services.plugin_installer.supervisor import default_supervisor
from services.plugin_installer.uv_installer import UvInstaller

logger = logging.getLogger(__name__)


_MANAGER: Optional[PluginInstallManager] = None
_RUNTIME: Optional[RuntimeConfig] = None


def _default_plugins_dir() -> Path:
    """Where installed plugins live on disk.

    Resolution order (first non-empty wins):
      1. ``MAGELLON_PLUGINS_INSTALL_DIR`` env var — operational override.
      2. ``app_settings.directory_settings.PLUGINS_DIR`` — fluent config
         (configs/app_settings_*.yaml). Relative paths resolve under
         MAGELLON_GPFS_PATH at load time.
      3. ``/var/magellon/plugins/installed`` — last-resort default.
    """
    import os
    env_override = os.environ.get("MAGELLON_PLUGINS_INSTALL_DIR")
    if env_override:
        return Path(env_override)
    try:
        from config import app_settings
        configured = getattr(app_settings.directory_settings, "PLUGINS_DIR", None)
        if configured:
            return Path(configured)
    except Exception:  # noqa: BLE001 — settings unavailable in some test paths
        pass
    return Path("/var/magellon/plugins/installed")


def _default_docker_network() -> Optional[str]:
    import os
    configured = os.environ.get("MAGELLON_DOCKER_NETWORK")
    if configured:
        return configured

    # Local Docker Desktop/dev compose uses this network and gives the
    # broker the DNS alias ``rabbitmq``. The CTF/MotionCor plugin images
    # read that alias from their bundled production settings, so installing
    # without the network starts a container that can never announce.
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "network", "inspect", "docker_magellon-network"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return "docker_magellon-network"
    except Exception:  # noqa: BLE001
        pass
    return None


def _build_runtime_config() -> RuntimeConfig:
    """Construct the deployment values plugins need at install time."""
    # Lazy-imported so the factory module doesn't pull settings on
    # import (settings touch the DB at construction time in some
    # configs).
    try:
        from config import app_settings
        rmq = app_settings.rabbitmq_settings
        broker_url = (
            f"amqp://{rmq.USER_NAME}:{rmq.PASSWORD}@{rmq.HOST_NAME}:{rmq.PORT}"
            f"/{rmq.VIRTUAL_HOST.lstrip('/')}"
        )
        gpfs_root = (
            getattr(app_settings.directory_settings, "MAGELLON_GPFS_PATH", None)
            or "/gpfs"
        )
    except Exception:  # noqa: BLE001 — settings unavailable in some test paths
        # Fall back to env vars so the factory still works in
        # bare-process scenarios.
        import os
        broker_url = os.environ.get(
            "MAGELLON_BROKER_URL", "amqp://guest:guest@localhost:5672/",
        )
        gpfs_root = os.environ.get(
            "MAGELLON_GPFS_PATH",
            os.environ.get("MAGELLON_HOME_DIR", "/gpfs"),
        )

    import os
    plugin_broker_override = os.environ.get("MAGELLON_PLUGIN_BROKER_URL")
    if plugin_broker_override:
        broker_url = plugin_broker_override

    extra_env: Dict[str, str] = {}
    # NATS_URL handed to plugins: operator override wins; otherwise
    # inherit from CoreService's own env. When unset on both sides we
    # leave it off so the SDK falls back to its built-in
    # ``nats://localhost:4222`` (and silently skips NATS publish if
    # nothing's listening there). The plugin's container-loopback is
    # not reachable from any broker, so docker deployments should always
    # set MAGELLON_PLUGIN_NATS_URL (e.g. ``nats://nats:4222`` on the
    # magellon docker network).
    plugin_nats = os.environ.get("MAGELLON_PLUGIN_NATS_URL") or os.environ.get("NATS_URL")
    if not plugin_nats and _default_docker_network() == "docker_magellon-network":
        plugin_nats = "nats://nats:4222"
    if plugin_nats:
        extra_env["NATS_URL"] = plugin_nats

    # COLUMNS controls the width Rich uses when rendering structured
    # log output. Containers run without a TTY, so Rich falls back to
    # 80 — every log line then hard-wraps at column 80 with deep
    # left-padding for the message column, which renders as a narrow
    # ~1/3-width text strip in the React Logs tab. 200 gives Rich
    # enough room to keep one log entry on one wire line, so the UI's
    # ``whiteSpace: 'pre'`` shows them at the natural width of the
    # browser viewport.
    extra_env.setdefault("COLUMNS", "200")

    return RuntimeConfig(broker_url=broker_url, gpfs_root=gpfs_root, extra_env=extra_env)


def _liveness_health_check(plugin_id: str, timeout_seconds: float) -> bool:
    """Poll the in-process :class:`PluginLivenessRegistry` for an
    announce from ``plugin_id`` within the timeout.

    Pre-1.1 this was a no-op (always True) — installs that announced
    successfully looked identical to installs that never came up.
    Wiring the real registry means the manager's post-install
    rollback path (``manager.py`` line ~280) now actually fires when
    a plugin fails to phone home.

    Lazy import: the SDK liveness module pulls bus modules that are
    not safe to import at factory construction time in some test
    paths. Resolving at call time keeps the factory cheap to import.
    """
    try:
        from magellon_sdk.bus.services.liveness_registry import get_registry
    except Exception:  # noqa: BLE001 — SDK shape changed or unimportable
        logger.warning(
            "health check: could not import liveness registry; "
            "treating install as successful",
        )
        return True

    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    interval = 0.5
    registry = get_registry()
    while True:
        for entry in registry.list_live():
            # Legacy CTF/MotionCor plugins announce PluginInfo.name
            # ("CTF Plugin") while the .mpn manifest uses the stable
            # archive id ("ctf"). Treat a live category match as healthy
            # for those single-backend category plugins.
            if entry.plugin_id == plugin_id:
                return True
            if (entry.category or "").lower() == plugin_id.lower():
                return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(interval)


def _build_manager() -> PluginInstallManager:
    plugins_dir = _default_plugins_dir()
    plugins_dir.mkdir(parents=True, exist_ok=True)
    network = _default_docker_network()
    installers = [
        UvInstaller(plugins_dir=plugins_dir),
        DockerInstaller(plugins_dir=plugins_dir, network=network),
    ]
    # Pass plugins_dir so the Popen supervisor (Windows / macOS dev)
    # can find install dirs + persist PID files. Linux production
    # still resolves to SystemdUserSupervisor, which doesn't need it.
    supervisor = default_supervisor(plugins_dir=plugins_dir)
    lifecycles = [
        UvLifecycle(supervisor),
        DockerLifecycle(plugins_dir=plugins_dir),
    ]
    return PluginInstallManager(
        installers, supervisor=supervisor, lifecycles=lifecycles,
        health_check=_liveness_health_check,
    )


def get_install_manager() -> PluginInstallManager:
    """FastAPI ``Depends`` target. First call constructs; subsequent
    calls return the cached instance. Tests inject a fake via
    ``app.dependency_overrides[get_install_manager]``."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = _build_manager()
    return _MANAGER


def get_runtime_config() -> RuntimeConfig:
    """Same pattern for the deployment-supplied runtime config."""
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = _build_runtime_config()
    return _RUNTIME


def reset_factory() -> None:
    """Test helper — drops the cached manager + runtime config so
    the next ``get_*`` call re-builds from scratch."""
    global _MANAGER, _RUNTIME
    _MANAGER = None
    _RUNTIME = None


__all__ = [
    "get_install_manager",
    "get_runtime_config",
    "reset_factory",
]
