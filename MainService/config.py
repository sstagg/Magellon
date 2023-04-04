import os

BASE_DIRECTORY = os.path.abspath(os.path.dirname(__file__))

BASE_PATH = r"C:\temp\data"
# BASE_PATH = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata"

# Database Connection information
# Sample postgresql
DB_Driver = 'postgresql+psycopg2'
DB_USER = 'postgres'
DB_PASSWORD = 'behd1d2'
DB_HOST = '192.168.92.133'
DB_Port = '5432'
DB_NAME = 'magellon03'

# Sample mysql
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon03'
# DB_Driver = 'mysql+pymysql'
# DB_USER = 'admin'
# DB_PASSWORD = 'behd1d2'
# DB_HOST = '192.168.92.133'
# DB_Port = '3306'
# DB_NAME = 'magellon03'
