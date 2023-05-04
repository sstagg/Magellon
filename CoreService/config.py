import os
import consul

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

if os.environ.get('APP_ENV', "development") == 'production':
    from config_prod import *
else:
    from config_dev import *

consul_client = None

try:
    # consul_client = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
    consul_client = consul.Consul(**consul_config)
except:
    consul_client = None


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


def get_db_connection():
    return f'{DB_Driver}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_Port}/{DB_NAME}'
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon04"
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon02?check_same_thread=False"
    # return os.getenv("DB_CONN")
