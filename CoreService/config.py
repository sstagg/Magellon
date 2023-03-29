import os

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

BASE_PATH = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata"
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon03'

# Database Connection information
# Sample postgresql
DB_Driver = 'postgresql+psycopg2'
DB_USER = 'postgres'
DB_PASSWORD = 'behd1d2'
DB_HOST = '192.168.92.133'
DB_Port = '5432'
DB_NAME = 'magellon04'


# Sample mysql
# DB_Driver = 'mysql+pymysql'
# DB_USER = 'admin'
# DB_PASSWORD = 'behd1d2'
# DB_HOST = '192.168.92.133'
# DB_Port = '3306'
# DB_NAME = 'magellon04'

def get_db_connection():
    return f'{DB_Driver}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_Port}/{DB_NAME}'
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon04"
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon02?check_same_thread=False"
    # return os.getenv("DB_CONN")
