import os

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))


# Create a connection to Consul agent
CONSUL_HOST = os.getenv('CONSUL_HOST', '192.168.92.133')
CONSUL_PORT = os.getenv('CONSUL_PORT', '8500')
CONSUL_USERNAME = os.getenv('CONSUL_USERNAME', '8500')
CONSUL_PASSWORD = os.getenv('CONSUL_PASSWORD', '8500')

consul_config = {
    "host": "192.168.92.133",
    "port": 8500
}

# BASE_PATH = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata"
IMAGE_ROOT_URL = r"http://localhost/cdn/"
IMAGE_SUB_URL = r"images/"
THUMBNAILS_SUB_URL = r"thumbnails/"
FFT_SUB_URL = r"FFTs/"

# my_config_value = os.environ.get('MY_CONFIG_VALUE')
IMAGE_ROOT_DIR = os.getenv('DATA_DIR', r'c:/temp/data')

IMAGES_DIR = f"{IMAGE_ROOT_DIR}/images/"
FFT_DIR = f"{IMAGE_ROOT_DIR}/FFTs/"
THUMBNAILS_DIR = f"{IMAGE_ROOT_DIR}/thumbnails/"
JOBS_DIR = f"{IMAGE_ROOT_DIR}/processing/"



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
DB_NAME = 'magellon01'