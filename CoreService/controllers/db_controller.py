from sqlalchemy.orm import Session
from sqlalchemy_utils import create_database, drop_database, database_exists
from database import get_db
from config import get_db_connection

from fastapi import APIRouter, Depends

from models.sqlalchemy_models import metadata

db_router = APIRouter()


@db_router.post("/create_database", tags=["Database"])
async def create_app_database(db_session: Session = Depends(get_db)):
    """Create the database and its tables."""
    if not database_exists(get_db_connection()):
        create_database(get_db_connection())  # db.bind.url
        metadata.create_all(db_session.bind)
        print("Database created successfully.")
    else:
        print("Database already exists.")
    return {"message": "Database created successfully."}


@db_router.post("/drop_database", tags=["Database"])
async def drop_app_database(db: Session = Depends(get_db)):
    """Drop the database and its tables."""
    if database_exists(get_db_connection()):
        drop_database(get_db_connection())  # db.bind.url
        print("Database dropped successfully.")
    else:
        print("Database already dropped.")
    return {"message": "Database dropped successfully."}


async def execute_sql(self, sql: str, db: Session = Depends(get_db()), params=None):
    with db.connect() as conn:
        result = conn.execute(sql, params)
        if result.returns_rows:
            return result.fetchall()
        else:
            return None
