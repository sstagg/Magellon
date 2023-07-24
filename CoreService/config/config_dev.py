import os
import uuid

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
ENV_TYPE = "development"
# Create a connection to Consul agent
CONSUL_HOST = os.getenv('CONSUL_HOST', '192.168.92.133')
CONSUL_PORT = os.getenv('CONSUL_PORT', '8500')
CONSUL_USERNAME = os.getenv('CONSUL_USERNAME', '8500')
CONSUL_PASSWORD = os.getenv('CONSUL_PASSWORD', '8500')

CONSUL_SERVICE_NAME = os.getenv('CONSUL_SERVICE_NAME', 'magellon-core-service')
CONSUL_SERVICE_ID = os.getenv('CONSUL_SERVICE_ID', "magellon-service-" + str(uuid.uuid4()))

consul_config = {
    "host": "192.168.92.133",
    "port": 8500
}

SLACK_TOKEN: str = os.getenv('SLACK_TOKEN') or "xoxb-5284990093169-5258053840439-aJ8x7uHcUCNqCKSZkbOSbAlq"

# BASE_PATH = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata"
IMAGE_ROOT_URL = r"http://localhost/cdn/"

ORIGINAL_IMAGES_SUB_URL = r"original/"
IMAGE_SUB_URL = r"images/"
THUMBNAILS_SUB_URL = r"thumbnails/"
FRAMES_SUB_URL = r"frames/"
FFT_SUB_URL = r"FFTs/"
JOBS_PROCESSING_SUB_URL = r"processing/"

THUMBNAILS_SUFFIX = r"_TIMG.png"
FRAMES_SUFFIX = r"_frame"
FFT_SUFFIX = r"_FFT.png"

# my_config_value = os.environ.get('MY_CONFIG_VALUE')
IMAGE_ROOT_DIR = os.getenv('DATA_DIR', r'c:/temp/data')

IMAGES_DIR = f"{IMAGE_ROOT_DIR}/{IMAGE_SUB_URL}"
FFT_DIR = f"{IMAGE_ROOT_DIR}/{FFT_SUB_URL}"
THUMBNAILS_DIR = f"{IMAGE_ROOT_DIR}/{THUMBNAILS_SUB_URL}"
JOBS_DIR = f"{IMAGE_ROOT_DIR}/{JOBS_PROCESSING_SUB_URL}"

# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon03'

# Database Connection information
# Sample postgresql
# DB_Driver = 'postgresql+psycopg2'
# DB_USER = 'postgres'
# DB_PASSWORD = 'behd1d2'
# DB_HOST = '192.168.92.133'
# DB_Port = '5432'
# DB_NAME = 'magellon05'

# mysql
# DB_Driver = 'mysql+pymysql'
# DB_USER = 'admin'
# DB_PASSWORD = 'behd1d2'
# DB_HOST = '192.168.92.133'
# DB_Port = '3306'
# DB_NAME = 'magellon05'

# mysql
DB_Driver = 'mysql+pymysql'
DB_USER = 'behdad'
DB_PASSWORD = 'behd1d#3454!2'
DB_HOST = '5.161.212.237'
DB_Port = '3306'
DB_NAME = 'magellon02'
