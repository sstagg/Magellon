import json
import os
import uuid
from typing import Any, Optional

import consul
from fastapi import FastAPI
from core.settings import AppSettingsSingleton

app_settings = AppSettingsSingleton.get_instance()

# consul_client: consul.Consul = None
consul_client= None

consul_config = {
    # "host": app_settings.LOCAL_IP_ADDRESS,
    "host": app_settings.consul_settings.CONSUL_HOST,
    "port": app_settings.consul_settings.CONSUL_PORT
}


def init_consul_client():
    global consul_client
    try:
        # consul_client = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        consul_client = consul.Consul(**consul_config)


    except:
        consul_client = None


def register_with_consul(app: FastAPI,
                         service_address: str,
                         service_name: str,
                         service_id: str,
                         service_port: int,
                         health_check_route: str):
    # Initialize Consul client
    # c = consul.Consul(host=consul_address, port=8500)

    # Register service with Consul
    consul_client.agent.service.register(
        name=service_name,
        service_id=str(uuid.uuid4()),
        address=service_address,
        port=service_port,
        check=consul.Check.http(url=f'http://{service_address}:{service_port}/{health_check_route}', interval='10s')
    )

    # Define shutdown function to deregister service when application is shut down
    def shutdown():
        consul_client.agent.service.deregister(service_id)

    # Add shutdown function to application events
    app.add_event_handler('shutdown', shutdown)


def get_kv_value(key: str, default: Optional[str] = None) -> str:
    """
    Retrieve a value from Consul Key-Value store or fallback to environment variables.

    Parameters:
    - key (str): The key to retrieve from Consul or environment variables.
    - default (Optional[str]): The default value to return if the key is not found (default is None).

    Returns:
    - str: The value associated with the key. If the key is not found, the default value is returned.

    Raises:
    - ValueError: If the key is not found in the Consul KV store.

    Consul-specific errors are caught and printed, and the function falls back to reading from
    environment variables using os.getenv() if Consul is not available or encounters an error.
    """
    try:
        if consul_client:
            _, key_value = consul_client.kv.get(key)

            if key_value is not None and 'Value' in key_value:
                return key_value['Value'].decode('utf-8')
            else:
                raise ValueError(f"{key} not found in Consul KV store")
    except consul.ConsulException as e:
        print(f"Consul error: {e}")

    return os.getenv(key, default)


def get_services(service_name:str) -> dict:
    # http://localhost:8500/v1/catalog/service/magellon-ctf-service
    try:
        if consul_client:
            key, services = consul_client.catalog.service(service_name)
            # for service in services:
            #     service_address = service.get("ServiceAddress")
            #     service_port = service.get("ServicePort")
            #     print(service_address,service_port,service)
            return services
    except (consul.ConsulException, json.JSONDecodeError) as e:
        print(f"Error fetching configurations: {e}")


def fetch_configurations() -> dict:
    """
    Fetch configurations from Consul Key-Value store.

    Returns:
    - dict: A dictionary containing configuration parameters.

    If Consul is not available or an error occurs during retrieval, returns None.
    """
    try:
        if consul_client:
            config_bytes = consul_client.kv.get('configurations')[1]['Value']
            config_str = config_bytes.decode('utf-8')
            config_dict = json.loads(config_str)
            # Uncomment and adjust the following line if there's a specific configuration key needed.
            # FFT_SUB_URL = config_dict.get('FFT_SUB_URL')
            return config_dict
    except (consul.ConsulException, json.JSONDecodeError) as e:
        print(f"Error fetching configurations: {e}")

    return None
