from fastapi import APIRouter, Depends
from sqlalchemy import text, Result
from sqlalchemy.orm import Session
from sqlalchemy_utils import create_database, drop_database, database_exists

from config import get_db_connection
from database import get_db
from models.sqlalchemy_models import metadata

db_router = APIRouter()


@db_router.post("/database")
async def create_app_database(db_session: Session = Depends(get_db)):
    """Create the database and its tables."""
    if not database_exists(get_db_connection()):
        create_database(get_db_connection())  # db.bind.url
        metadata.create_all(db_session.bind)
        print("Database created successfully.")
    else:
        print("Database already exists.")
    return {"message": "Database created successfully."}


@db_router.delete("/database")
async def drop_app_database():
    """Drop the database and its tables."""
    return {"message": "Database dropped disabled for security reasons."}
    if database_exists(get_db_connection()):
        drop_database(get_db_connection())  # db.bind.url
        print("Database dropped successfully.")
    else:
        print("Database already dropped.")
    return {"message": "Database dropped successfully."}


async def execute_sql(sql: str, db: Session = Depends(get_db())):
    result_proxy: Result = db.execute(text(sql))
    # Convert the query results into a list of dictionaries.
    result_list = [dict(row) for row in result_proxy.fetchall()]

    return result_list
