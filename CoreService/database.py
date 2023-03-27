
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# engine = create_engine(get_db_connection(), connect_args={"check_same_thread": False})
def get_db_connection():
    return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon04"
    # return "mysql+pymysql://admin:behd1d2@192.168.92.133:3306/magellon02?check_same_thread=False"
    # return os.getenv("DB_CONN")


engine = create_engine(get_db_connection())
session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
