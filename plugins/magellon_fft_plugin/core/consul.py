"""Compatibility shim — binds this plugin's settings to the shared SDK consul helpers."""
from core.settings import AppSettingsSingleton
from magellon_sdk.config import consul as _sdk_consul
from magellon_sdk.config.consul import (  # noqa: F401
    fetch_configurations,
    get_kv_value,
    get_services,
    register_with_consul,
)


def init_consul_client() -> None:
    s = AppSettingsSingleton.get_instance()
    _sdk_consul.init_consul_client(
        host=s.consul_settings.CONSUL_HOST,
        port=s.consul_settings.CONSUL_PORT,
    )


__all__ = [
    "fetch_configurations",
    "get_kv_value",
    "get_services",
    "init_consul_client",
    "register_with_consul",
]
