import os

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

# BASE_PATH = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata"
IMAGE_ROOT_URL = r"http://localhost/cdn/"
IMAGE_SUB_URL = r"images/"
THUMBNAILS_SUB_URL = r"thumbnails/"

IMAGE_ROOT_DIR = r"C:\temp\data"
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


def get_db_connection():
    return f'{DB_Driver}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_Port}/{DB_NAME}'
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon04"
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon02?check_same_thread=False"
    # return os.getenv("DB_CONN")
