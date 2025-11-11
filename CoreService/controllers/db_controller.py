from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy_utils import create_database, drop_database, database_exists
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
    _: None = Depends(require_role('Administrator')),  # ✅ Admin-only
    user_id: UUID = Depends(get_current_user_id)       # ✅ Audit trail
):
    """
    Create the database and its tables.

    **Requires:** Administrator role
    **Security:** Only administrators can create database schema
    """
    logger.warning(f"User {user_id} initiating database schema creation")

    if not database_exists(get_db_connection()):
        create_database(get_db_connection())  # db.bind.url
        metadata.create_all(db_session.bind)
        logger.info(f"Database schema created successfully by user {user_id}")
        return {
            "message": "Database created successfully.",
            "created_by": str(user_id)
        }
    else:
        logger.info(f"User {user_id} attempted to create database, but it already exists")
        return {
            "message": "Database already exists.",
            "checked_by": str(user_id)
        }


@db_router.delete("/database")
async def drop_app_database(
    _: None = Depends(require_role('Administrator')),  # ✅ Admin-only
    user_id: UUID = Depends(get_current_user_id)       # ✅ Audit trail
):
    """
    Drop the database and its tables.

    **WARNING:** This is a destructive operation that will delete all data!
    **Requires:** Administrator role
    **Status:** Currently disabled for safety
    """
    logger.critical(
        f"User {user_id} attempted to drop database - OPERATION DISABLED FOR SAFETY"
    )
    return {
        "message": "Database drop is disabled for security reasons.",
        "requested_by": str(user_id),
        "note": "To enable this operation, remove the early return in the code."
    }

    # Disabled code below - uncomment only if you really need this functionality
    # if database_exists(get_db_connection()):
    #     drop_database(get_db_connection())
    #     logger.critical(f"Database dropped by user {user_id} - ALL DATA LOST")
    #     return {"message": "Database dropped successfully.", "dropped_by": str(user_id)}
    # else:
    #     logger.info(f"User {user_id} attempted to drop database, but it doesn't exist")
    #     return {"message": "Database already dropped.", "checked_by": str(user_id)}


# async def execute_sql(sql: str, db: Session = Depends(get_db())):
#     result_proxy: Result = db.execute(text(sql))
#     # Convert the query results into a list of dictionaries.
#     result_list = [dict(row) for row in result_proxy.fetchall()]
#
#     return result_list
