import os
import uuid
ENV_TYPE = "production"



# BASE_PATH = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata"
IMAGE_ROOT_URL = r"http://localhost/cdn/"

ORIGINAL_IMAGES_SUB_URL = r"original/"
IMAGE_SUB_URL = r"images/"
FRAMES_SUB_URL = r"frames/"
THUMBNAILS_SUB_URL = r"thumbnails/"
FFT_SUB_URL = r"ffts/"
JOBS_PROCESSING_SUB_URL = r"processing/"

THUMBNAILS_SUFFIX = r"_thumbs.png"
FRAMES_SUFFIX = r"_frame"
FFT_SUFFIX = r"_fft.png"


# my_config_value = os.environ.get('MY_CONFIG_VALUE')
IMAGE_ROOT_DIR = os.getenv('DATA_DIR', '/app/data')

IMAGES_DIR = f"{IMAGE_ROOT_DIR}/{IMAGE_SUB_URL}"
FFT_DIR = f"{IMAGE_ROOT_DIR}/{FFT_SUB_URL}"
THUMBNAILS_DIR = f"{IMAGE_ROOT_DIR}/{THUMBNAILS_SUB_URL}"
JOBS_DIR = f"{IMAGE_ROOT_DIR}/{JOBS_PROCESSING_SUB_URL}"


# Database Connection information
# Sample postgresql
# DB_Driver = 'postgresql+psycopg2'
# DB_USER = 'postgres'
# DB_PASSWORD = 'behd1d2'
# DB_HOST = '192.168.92.133'
# DB_Port = '5432'
# DB_NAME = 'magellon05'



