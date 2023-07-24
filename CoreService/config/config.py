import json
import os
import consul
import yaml
import uuid
from fastapi import FastAPI

from models.pydantic_models_settings import AppSettings, ConsulSettings, DirectorySettings, DatabaseSettings

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
# Initialize AppSettings instance with default values or fallback settings
app_settings = AppSettings(
    consul_settings=ConsulSettings(
        CONSUL_HOST=os.getenv('CONSUL_HOST', '192.168.92.133'),
        CONSUL_PORT=os.getenv('CONSUL_PORT', 8500),
        CONSUL_USERNAME=os.getenv('CONSUL_USERNAME', '8500'),
        CONSUL_PASSWORD=os.getenv('CONSUL_PASSWORD', '8500'),
        CONSUL_SERVICE_NAME=os.getenv('CONSUL_SERVICE_NAME', 'magellon-core-service'),
        CONSUL_SERVICE_ID=os.getenv('CONSUL_SERVICE_ID', "magellon-service-" + str(uuid.uuid4()))

    ),
    directory_settings=DirectorySettings(
        IMAGE_ROOT_URL=r"http://localhost/cdn/",
        ORIGINAL_IMAGES_SUB_URL=r'original/',
        IMAGE_SUB_URL=r'images/',
        THUMBNAILS_SUB_URL=r'thumbnails/',
        FRAMES_SUB_URL=r'frames/',
        FFT_SUB_URL=r'FFTs/',
        JOBS_PROCESSING_SUB_URL=r'processing/',
        THUMBNAILS_SUFFIX=r'_TIMG.png',
        FRAMES_SUFFIX=r'_frame',
        FFT_SUFFIX=r'_fft.png',
        IMAGE_ROOT_DIR=os.getenv('DATA_DIR', r'c:/temp/data'),
        # IMAGES_DIR=f"{IMAGE_ROOT_DIR}/{IMAGE_SUB_URL}",
        # FFT_DIR=f"{IMAGE_ROOT_DIR}/{FFT_SUB_URL}",
        # THUMBNAILS_DIR= f"{IMAGE_ROOT_DIR}/{THUMBNAILS_SUB_URL}",
        # JOBS_DIR=f"{IMAGE_ROOT_DIR}/{JOBS_PROCESSING_SUB_URL}"
    ),
    database_settings=DatabaseSettings(
        DB_Driver='mysql+pymysql',
        DB_USER='behdad',
        DB_PASSWORD='behd1d#3454!2',
        DB_HOST='5.161.212.237',
        DB_Port=3306,
        DB_NAME='magellon02'
    ),
    SLACK_TOKEN=os.getenv('SLACK_TOKEN') or "xoxb-5284990093169-5258053840439-aJ8x7uHcUCNqCKSZkbOSbAlq",
    BASE_DIRECTORY=os.path.abspath(os.path.dirname(__file__)),
    ENV_TYPE='development',
)
# with open("./app_settings_prod.yaml", "w") as file:
#     yaml.dump(app_settings.dict(), file)
# app_settings.save_settings("./app_settings_prod2.yaml")

if os.environ.get('APP_ENV', "development") == 'production':
    from .config_prod import *
    app_settings = AppSettings.load_settings("./config/app_settings_prod.yaml")
else:
    from .config_dev import *
    app_settings = AppSettings.load_settings("./config/app_settings_dev.yaml")

consul_client = None

consul_config = {
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
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon04"
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon02?check_same_thread=False"
    # return os.getenv("DB_CONN")

#
# # Display the initialized values
# print(app_settings.dict())
