import os
import consul

from models.pydantic_models_settings import AppSettings

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
DEFECTS_SUB_URL = app_settings.directory_settings.DEFECTS_SUB_URL
FFT_SUB_URL = app_settings.directory_settings.FFT_SUB_URL
JOBS_PROCESSING_SUB_URL = app_settings.directory_settings.JOBS_PROCESSING_SUB_URL

THUMBNAILS_SUFFIX = app_settings.directory_settings.THUMBNAILS_SUFFIX
FRAMES_SUFFIX = app_settings.directory_settings.FRAMES_SUFFIX
FFT_SUFFIX = app_settings.directory_settings.FFT_SUFFIX
ATLAS_SUFFIX = app_settings.directory_settings.ATLAS_SUFFIX

# my_config_value = os.environ.get('MY_CONFIG_VALUE')
MAGELLON_HOME_DIR = app_settings.directory_settings.MAGELLON_HOME_DIR or os.getenv('DATA_DIR', '/app/data')
MAGELLON_JOBS_DIR = app_settings.directory_settings.JOBS_DIR or os.getenv('MAGELLON_JOBS_PATH', '/jobs')
MAGELLON_GPFS_DIR = app_settings.directory_settings.MAGELLON_GPFS_PATH or os.getenv('MAGELLON_GPFS_PATH', '/gpfs')
IMAGES_DIR = f"{MAGELLON_HOME_DIR}/{IMAGE_SUB_URL}"
FFT_DIR = f"{MAGELLON_HOME_DIR}/{FFT_SUB_URL}"
THUMBNAILS_DIR = f"{MAGELLON_HOME_DIR}/{THUMBNAILS_SUB_URL}"
JOBS_DIR = f"{MAGELLON_HOME_DIR}/{JOBS_PROCESSING_SUB_URL}"


DOCKER_URL = app_settings.DOCKER_URL
DOCKER_USERNAME = app_settings.DOCKER_USERNAME
DOCKER_PASSWORD = app_settings.DOCKER_PASSWORD


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


def get_db_connection():
    return f'{app_settings.database_settings.DB_Driver}://{app_settings.database_settings.DB_USER}:{app_settings.database_settings.DB_PASSWORD}@{app_settings.database_settings.DB_HOST}:{app_settings.database_settings.DB_Port}/{app_settings.database_settings.DB_NAME}'
