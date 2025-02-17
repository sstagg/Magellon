import json
import os
import consul
from fastapi import FastAPI

from models.pydantic_models_settings import AppSettings, ConsulSettings, DirectorySettings, DatabaseSettings

# from services.file_service import create_directory

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
# Initialize AppSettings instance with default values or fallback settings

app_settings: AppSettings = None

if os.environ.get('APP_ENV', "development") == 'production':
    # from .config_prod import *
    app_settings = AppSettings.load_settings("./configs/app_settings_prod.yaml")
else:
    # from .config_dev import *
    app_settings = AppSettings.load_settings("./configs/app_settings_dev.yaml")

consul_client = None

consul_config = {
    "host": app_settings.consul_settings.CONSUL_HOST,
    "port": app_settings.consul_settings.CONSUL_PORT
}

IMAGE_ROOT_URL = app_settings.directory_settings.IMAGE_ROOT_URL

ORIGINAL_IMAGES_SUB_URL = app_settings.directory_settings.ORIGINAL_IMAGES_SUB_URL
IMAGE_SUB_URL = app_settings.directory_settings.IMAGE_SUB_URL
FRAMES_SUB_URL = app_settings.directory_settings.FRAMES_SUB_URL
THUMBNAILS_SUB_URL = app_settings.directory_settings.THUMBNAILS_SUB_URL
ATLAS_SUB_URL = app_settings.directory_settings.ATLAS_SUB_URL
CTF_SUB_URL = app_settings.directory_settings.CTF_SUB_URL
FAO_SUB_URL = app_settings.directory_settings.FAO_SUB_URL
GAINS_SUB_URL = app_settings.directory_settings.GAIN_SUB_URL
FFT_SUB_URL = app_settings.directory_settings.FFT_SUB_URL
JOBS_PROCESSING_SUB_URL = app_settings.directory_settings.JOBS_PROCESSING_SUB_URL

THUMBNAILS_SUFFIX = app_settings.directory_settings.THUMBNAILS_SUFFIX
FRAMES_SUFFIX = app_settings.directory_settings.FRAMES_SUFFIX
FFT_SUFFIX = app_settings.directory_settings.FFT_SUFFIX
ATLAS_SUFFIX = app_settings.directory_settings.ATLAS_SUFFIX

# my_config_value = os.environ.get('MY_CONFIG_VALUE')
MAGELLON_HOME_DIR = app_settings.directory_settings.MAGELLON_HOME_DIR or os.getenv('DATA_DIR', '/app/data')

IMAGES_DIR = f"{MAGELLON_HOME_DIR}/{IMAGE_SUB_URL}"
FFT_DIR = f"{MAGELLON_HOME_DIR}/{FFT_SUB_URL}"
THUMBNAILS_DIR = f"{MAGELLON_HOME_DIR}/{THUMBNAILS_SUB_URL}"
JOBS_DIR = f"{MAGELLON_HOME_DIR}/{JOBS_PROCESSING_SUB_URL}"


DOCKER_URL = app_settings.DOCKER_URL
DOCKER_USERNAME = app_settings.DOCKER_REPOSITORY
DOCKER_USERNAME = app_settings.DOCKER_USERNAME
DOCKER_PASSWORD = app_settings.DOCKER_PASSWORD


def init_consul_client():
    global consul_client
    try:
        # consul_client = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        consul_client = consul.Consul(**consul_config)

    except:
        consul_client = None


# init_consul_client()


def register_with_consul(app: FastAPI, service_address: str, service_name: str, service_id: str, service_port: int,
                         health_check_route: str):
    # Initialize Consul client
    # c = consul.Consul(host=consul_address, port=8500)

    # Register service with Consul
    consul_client.agent.service.register(
        name=service_name,
        service_id=service_id,
        address=service_address,
        port=service_port,
        check=consul.Check.http(url=f'http://{service_address}:{service_port}/{health_check_route}', interval='10s')
    )

    # Define shutdown function to deregister service when application is shut down
    def shutdown():
        consul_client.agent.service.deregister(service_id)

    # Add shutdown function to application events
    app.add_event_handler('shutdown', shutdown)


# Define a function to retrieve the image root directory configuration
def fetch_image_root_dir():
    if consul_client:
        try:
            _, image_root_dir_kv = consul_client.kv.get('IMAGE_ROOT_DIR')
            if image_root_dir_kv is None:
                raise ValueError("IMAGE_ROOT_DIR not found in Consul KV store")
            return image_root_dir_kv['Value']
        except:
            pass

    return os.getenv('DATA_DIR', '/app/data')


def fetch_configurations():
    if consul_client:
        try:
            config_bytes = consul_client.kv.get('configurations')[1]['Value']
            config_str = config_bytes.decode('utf-8')
            config_dict = json.loads(config_str)
            # FFT_SUB_URL = config_dict['FFT_SUB_URL']
            return config_dict
        except:
            pass
    return None


def get_db_connection():
    return f'{app_settings.database_settings.DB_Driver}://{app_settings.database_settings.DB_USER}:{app_settings.database_settings.DB_PASSWORD}@{app_settings.database_settings.DB_HOST}:{app_settings.database_settings.DB_Port}/{app_settings.database_settings.DB_NAME}'
