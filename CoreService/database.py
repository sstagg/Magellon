
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import get_db_connection

# engine = create_engine(get_db_connection(), connect_args={"check_same_thread": False})
engine = create_engine(get_db_connection())
session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
