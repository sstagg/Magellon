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
from pathlib import Path
from typing import Optional

from services.plugin_installer.docker_installer import DockerInstaller
from services.plugin_installer.manager import PluginInstallManager
from services.plugin_installer.protocol import RuntimeConfig
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
    return os.environ.get("MAGELLON_DOCKER_NETWORK") or None


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
        gpfs_root = getattr(app_settings, "MAGELLON_HOME_DIR", None) or "/gpfs"
    except Exception:  # noqa: BLE001 — settings unavailable in some test paths
        # Fall back to env vars so the factory still works in
        # bare-process scenarios.
        import os
        broker_url = os.environ.get(
            "MAGELLON_BROKER_URL", "amqp://guest:guest@localhost:5672/",
        )
        gpfs_root = os.environ.get("MAGELLON_HOME_DIR", "/gpfs")

    return RuntimeConfig(broker_url=broker_url, gpfs_root=gpfs_root)


def _build_manager() -> PluginInstallManager:
    plugins_dir = _default_plugins_dir()
    plugins_dir.mkdir(parents=True, exist_ok=True)
    network = _default_docker_network()
    installers = [
        UvInstaller(plugins_dir=plugins_dir),
        DockerInstaller(plugins_dir=plugins_dir, network=network),
    ]
    return PluginInstallManager(installers)


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
