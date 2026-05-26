from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy_utils import create_database, database_exists
from uuid import UUID
import logging

from config import get_db_connection
from database import get_db
from models.sqlalchemy_models import metadata
from dependencies.permissions import require_role
from dependencies.auth import get_current_user_id

logger = logging.getLogger(__name__)
db_router = APIRouter()


@db_router.post("/database")
async def create_app_database(
    db_session: Session = Depends(get_db),
    _: None = Depends(require_role("Administrator")),
    user_id: UUID = Depends(get_current_user_id),
):
    """
    Create the database and its tables.

    **Requires:** Administrator role
    **Security:** Only administrators can create database schema
    """
    logger.warning(f"User {user_id} initiating database schema creation")

    if not database_exists(get_db_connection()):
        create_database(get_db_connection())
        metadata.create_all(db_session.bind)
        logger.info(f"Database schema created successfully by user {user_id}")
        return {
            "message": "Database created successfully.",
            "created_by": str(user_id),
        }

    logger.info(f"User {user_id} attempted to create database, but it already exists")
    return {
        "message": "Database already exists.",
        "checked_by": str(user_id),
    }
