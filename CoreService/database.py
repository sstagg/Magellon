from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import get_db_connection

engine = create_engine(get_db_connection())
session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    try:
        db = session_local()
        yield db
    finally:
        db.close()
