import os
import uuid

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))
ENV_TYPE = "development"

# SLACK_TOKEN: str = os.getenv('SLACK_TOKEN') or "xoxb-5284990093169-5258053840439-aJ8x7uHcUCNqCKSZkbOSbAlq"

# BASE_PATH = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata"
IMAGE_ROOT_URL = r"http://localhost/cdn/"

ORIGINAL_IMAGES_SUB_URL = r"original/"
IMAGE_SUB_URL = r"images/"
THUMBNAILS_SUB_URL = r"thumbnails/"
FRAMES_SUB_URL = r"frames/"
FFT_SUB_URL = r"ffts/"
JOBS_PROCESSING_SUB_URL = r"processing/"

THUMBNAILS_SUFFIX = r"_TIMG.png"
FRAMES_SUFFIX = r"_frame"
FFT_SUFFIX = r"_fft.png"

# my_config_value = os.environ.get('MY_CONFIG_VALUE')
IMAGE_ROOT_DIR = os.getenv('DATA_DIR', r'c:/temp/data')

IMAGES_DIR = f"{IMAGE_ROOT_DIR}/{IMAGE_SUB_URL}"
FFT_DIR = f"{IMAGE_ROOT_DIR}/{FFT_SUB_URL}"
THUMBNAILS_DIR = f"{IMAGE_ROOT_DIR}/{THUMBNAILS_SUB_URL}"
JOBS_DIR = f"{IMAGE_ROOT_DIR}/{JOBS_PROCESSING_SUB_URL}"

