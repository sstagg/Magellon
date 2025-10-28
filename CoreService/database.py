from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging

from config import get_db_connection

# Configure SQLAlchemy logging - set to WARNING to reduce noise
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Create engine with connection pooling
engine = create_engine(
    get_db_connection(),
    pool_size=5,           # Maintain 5 connections in the pool
    max_overflow=10,       # Allow up to 10 additional connections
    pool_pre_ping=True,    # Verify connections before using them
    pool_recycle=3600,     # Recycle connections after 1 hour
    echo=False             # Disable SQL echo (set to True for debugging)
)

session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    try:
        db = session_local()
        yield db
    finally:
        db.close()
