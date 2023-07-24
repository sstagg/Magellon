import json
import os
import consul
from fastapi import FastAPI

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

if os.environ.get('APP_ENV', "development") == 'production':
    from .config_prod import *
else:
    from .config_dev import *

consul_client = None


def init_consul_client():
    global consul_client
    try:
        # consul_client = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        consul_client = consul.Consul(**consul_config)

    except:
        consul_client = None


init_consul_client()


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
    return f'{DB_Driver}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_Port}/{DB_NAME}'
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon04"
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon02?check_same_thread=False"
    # return os.getenv("DB_CONN")



# Initialize AppSettings instance with custom values
# app_settings = AppSettings(
#     consul_settings=ConsulSettings(
#         CONSUL_HOST='192.168.1.100',
#         CONSUL_PORT=8501,
#         CONSUL_USERNAME='myconsuluser',
#         CONSUL_PASSWORD='myconsulpassword',
#         CONSUL_SERVICE_NAME='my-service',
#         CONSUL_SERVICE_ID='my-service-id'
#     ),
#     directory_settings=DirectorySettings(
#         IMAGE_ROOT_URL='http://example.com/cdn/',
#         ORIGINAL_IMAGES_SUB_URL='original/',
#         IMAGE_SUB_URL='images/',
#         THUMBNAILS_SUB_URL='thumbnails/',
#         FRAMES_SUB_URL='frames/',
#         FFT_SUB_URL='FFTs/',
#         JOBS_PROCESSING_SUB_URL='processing/',
#         THUMBNAILS_SUFFIX='_thumb.png',
#         FRAMES_SUFFIX='_frame',
#         FFT_SUFFIX='_fft.png',
#         IMAGE_ROOT_DIR='/path/to/data',
#         IMAGES_DIR='/path/to/data/images/',
#         FFT_DIR='/path/to/data/FFTs/',
#         THUMBNAILS_DIR='/path/to/data/thumbnails/',
#         JOBS_DIR='/path/to/data/processing/'
#     ),
#     database_settings=DatabaseSettings(
#         DB_Driver='mysql+pymysql',
#         DB_USER='myuser',
#         DB_PASSWORD='mypassword',
#         DB_HOST='localhost',
#         DB_Port='3306',
#         DB_NAME='mydb'
#     ),
#     SLACK_TOKEN='xoxb-1234567890-abcdefghij-klmnopqrstuv-wxyz',
#     BASE_DIRECTORY='/path/to/base/directory',
#     ENV_TYPE='production'
# )
#
# # Display the initialized values
# print(app_settings.dict())