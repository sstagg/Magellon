from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import logging
import os

from config import get_db_connection

# Configure SQLAlchemy logging - set to WARNING to reduce noise
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return int(value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

# Create engine with connection pooling
engine = create_engine(
    get_db_connection(),
    pool_size=_env_int("MAGELLON_DB_POOL_SIZE", 5),
    max_overflow=_env_int("MAGELLON_DB_MAX_OVERFLOW", 10),
    pool_timeout=_env_int("MAGELLON_DB_POOL_TIMEOUT", 30),
    pool_pre_ping=True,    # Verify connections before using them
    pool_recycle=_env_int("MAGELLON_DB_POOL_RECYCLE", 3600),
    echo=_env_bool("MAGELLON_DB_ECHO", False),
)

session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    try:
        db = session_local()
        yield db
    finally:
        db.close()
