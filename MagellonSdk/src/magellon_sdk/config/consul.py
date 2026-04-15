"""Consul helpers shared by Magellon plugins.

The four plugin copies of ``core/consul.py`` all differed only in a
commented-out line. This module owns the consul client and the four
helpers; plugins pass ``host`` and ``port`` into
:func:`init_consul_client` explicitly so the SDK does not need to know
how each plugin stores its settings.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import consul
from fastapi import FastAPI

consul_client: Optional[Any] = None


def init_consul_client(host: Optional[str], port: Optional[int]) -> None:
    global consul_client
    try:
        consul_client = consul.Consul(host=host, port=port)
    except Exception:
        consul_client = None


def register_with_consul(
    app: FastAPI,
    service_address: str,
    service_name: str,
    service_id: str,
    service_port: int,
    health_check_route: str,
) -> None:
    consul_client.agent.service.register(
        name=service_name,
        service_id=service_id,
        address=service_address,
        port=service_port,
        check=consul.Check.http(
            url=f"http://{service_address}:{service_port}/{health_check_route}",
            interval="10s",
        ),
    )

    def shutdown() -> None:
        consul_client.agent.service.deregister(service_id)

    app.add_event_handler("shutdown", shutdown)


def get_kv_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read ``key`` from Consul KV, falling back to the environment variable."""
    try:
        if consul_client:
            _, key_value = consul_client.kv.get(key)
            if key_value is not None and "Value" in key_value:
                return key_value["Value"].decode("utf-8")
            raise ValueError(f"{key} not found in Consul KV store")
    except consul.ConsulException as e:
        print(f"Consul error: {e}")

    return os.getenv(key, default)


def get_services(service_name: str) -> Optional[dict]:
    try:
        if consul_client:
            _, services = consul_client.catalog.service(service_name)
            return services
    except (consul.ConsulException, json.JSONDecodeError) as e:
        print(f"Error fetching configurations: {e}")
    return None


def fetch_configurations() -> Optional[dict]:
    try:
        if consul_client:
            config_bytes = consul_client.kv.get("configurations")[1]["Value"]
            config_str = config_bytes.decode("utf-8")
            return json.loads(config_str)
    except (consul.ConsulException, json.JSONDecodeError) as e:
        print(f"Error fetching configurations: {e}")
    return None
