import os
import re
import uuid
from typing import List
from uuid import UUID

import pymysql
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from config import ATLAS_SUB_URL, app_settings
from database import get_db
from lib.image_not_found import get_image_not_found
from models.pydantic_models import AtlasDto
from models.sqlalchemy_models import Atlas, Msession
from services.atlas import create_atlas_images
import logging

# Row-Level Security imports
from core.sqlalchemy_row_level_security import check_session_access
from dependencies.auth import get_current_user_id

atlas_router = APIRouter()

logger = logging.getLogger(__name__)


@atlas_router.get("/atlases", response_model=List[AtlasDto])
async def get_session_atlases(
    session_name: str,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get all atlases for a session.

    **Requires:** Authentication
    **Security:** User must have access to the session
    """
    logger.debug(f"User {user_id} requesting atlases for session: {session_name}")

    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if msession is None:
        return {"error": "Session not found"}

    # ✅ Check session access
    if not check_session_access(user_id, msession.oid, action="read"):
        logger.warning(f"SECURITY: User {user_id} denied atlas access for session: {session_name}")
        raise HTTPException(status_code=403, detail="Access denied to this session")

    try:
        return db_session.query(Atlas).filter(Atlas.session_id == msession.oid).all()
    # session_id_binary = msession.Oid.bytes
    except AttributeError:
        return {"error": "Invalid session ID"}


@atlas_router.get("/atlas-image")
async def get_atlas_image(
    name: str,
    sessionName: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get atlas image file.

    **Requires:** Authentication
    **Security:** User must have access to the session
    """
    if sessionName:
        session_name = sessionName.lower()
    else:
        underscore_index = name.find('_')
        session_name = name[:underscore_index].lower()

    logger.debug(f"User {user_id} requesting atlas image: {name} from session: {session_name}")

    # ✅ Verify session exists and check access
    db_session = next(get_db())
    try:
        msession = db_session.query(Msession).filter(Msession.name == session_name).first()
        if not msession:
            raise HTTPException(status_code=404, detail="Session not found")

        if not check_session_access(user_id, msession.oid, action="read"):
            logger.warning(f"SECURITY: User {user_id} denied atlas image access for session: {session_name}")
            raise HTTPException(status_code=403, detail="Access denied to this session")
    finally:
        db_session.close()

    file_path = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name}/{ATLAS_SUB_URL}/{name}.png"

    # Check if the file exists
    if not os.path.exists(file_path):
        return get_image_not_found()

    return FileResponse(file_path, media_type='image/png')


@atlas_router.get("/create_atlas")
def create_leginon_atlas(
    session_name: str,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Create Leginon atlas for a session.

    **Requires:** Authentication
    **Security:** User must have access to the session
    **WARNING:** This endpoint connects to external Leginon database
    """
    logger.warning(f"User {user_id} creating Leginon atlas for session: {session_name}")

    # Verify session exists and user has access
    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if not msession:
        raise HTTPException(status_code=404, detail="Session not found")

    # ✅ Check session access
    if not check_session_access(user_id, msession.oid, action="write"):
        logger.warning(f"SECURITY: User {user_id} denied atlas creation for session: {session_name}")
        raise HTTPException(status_code=403, detail="Access denied to this session")

    # ✅ SECURITY FIX: Load credentials from secure configuration
    if not app_settings.leginon_db_settings.ENABLED:
        logger.error("Leginon database integration is not enabled in configuration")
        raise HTTPException(
            status_code=503,
            detail="Leginon database integration is not configured. Please contact administrator."
        )

    if not app_settings.leginon_db_settings.PASSWORD:
        logger.error("Leginon database password not configured")
        raise HTTPException(
            status_code=503,
            detail="Leginon database credentials not configured. Please contact administrator."
        )

    db_config = {
        "host": app_settings.leginon_db_settings.HOST,
        "port": app_settings.leginon_db_settings.PORT,
        "user": app_settings.leginon_db_settings.USER,
        "password": app_settings.leginon_db_settings.PASSWORD,
        "db": app_settings.leginon_db_settings.DATABASE,
        "charset": "utf8",
    }

    logger.info(f"Connecting to Leginon database at {db_config['host']}:{db_config['port']}")
    connection = pymysql.connect(**db_config)  # Create a cursor to interact with the database
    cursor = connection.cursor()  # Define the SQL query for the first query

    query = "SELECT SessionData.DEF_id FROM SessionData WHERE SessionData.name = %s"
    cursor.execute(query, (session_name,))
    session_id = cursor.fetchone()[0]

    query1 = "SELECT * FROM ImageTargetListData WHERE `REF|SessionData|session` = %s AND mosaic = %s"

    mosaic_value = 1  # Execute the first query with parameters
    cursor.execute(query1, (session_id, mosaic_value))  # Fetch all the label results into a Python array
    label_values = [row[0] for row in cursor.fetchall()]  # Define the SQL query for the second query

    query2 = """
        SELECT a.DEF_id, SQRT(a.pixels) as dimx, SQRT(a.pixels) as dimy, a.filename,
               t.`delta row`, t.`delta column`
        FROM AcquisitionImageData a
        LEFT JOIN AcquisitionImageTargetData t ON a.`REF|AcquisitionImageTargetData|target` = t.DEF_id
        WHERE a.`REF|SessionData|session` = %s AND a.label = %s
    """
    label = "Grid"
    # Execute the second query with parameters
    cursor.execute(query2, (session_id, label))
    # Fetch all the results from the second query
    second_query_results = cursor.fetchall()
    # Create a dictionary to store grouped objects by label

    label_objects = {}

    for row in second_query_results:
        filename_parts = row[3].split("_")
        label_match = None
        for part in filename_parts:
            if part in label_values:
                label_match = part
                break

        if label_match:
            obj = {
                "id": row[0],
                "dimx": row[1],
                "dimy": row[2],
                "filename": row[3],
                "delta_row": row[4],
                "delta_column": row[5]
            }
            if label_match in label_objects:
                label_objects[label_match].append(obj)
            else:
                label_objects[label_match] = [obj]

    # Close the cursor and the database connection
    cursor.close()
    connection.close()

    images =  create_atlas_images(session_name, label_objects)

    atlases_to_insert = []
    for image in images:
        file_name = os.path.basename(image['imageFilePath'])
        file_name_without_extension = os.path.splitext(file_name)[0]
        atlas = Atlas(Oid=str(uuid.uuid4()), name=file_name_without_extension, meta=image['imageMap'])
        atlases_to_insert.append(atlas)
    # db_session.add_all(atlases_to_insert)
    db_session.bulk_save_objects(atlases_to_insert)
    db_session.commit()

    logger.info(f"User {user_id} successfully created Leginon atlas for session: {session_name}, {len(images)} images")
    return {"images": images, "created_by": str(user_id)}



def extract_grid_label(filename: str) -> str:
    """
    Extracts the grid name from a file name.
    The grid name is assumed to be a substring starting with an underscore and
    containing letters/numbers, followed by another underscore.

    Parameters:
        filename (str): The file name to process.

    Returns:
        str: The extracted grid name, or 'empty' if no grid name is found.
    """
    # Regular expression to match the grid name pattern (e.g., _g4d_)
    match = re.search(r'_([a-zA-Z0-9]+)_', filename)

    # Return the grid name or 'empty' if not found
    return match.group(1) if match else "empty"

@atlas_router.get("/create_magellon_atlas")
def create_magellon_atlas(
    session_name: str,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Create atlas images for a Magellon session using the Image table.

    **Requires:** Authentication
    **Security:** User must have write access to the session
    """
    try:
        logger.warning(f"User {user_id} creating Magellon atlas for session: {session_name}")

        # Get the session ID from Msession table
        msession = db_session.query(Msession).filter(Msession.name == session_name).first()
        if not msession:
            raise HTTPException(status_code=404, detail="Session not found")

        # ✅ Check session access
        if not check_session_access(user_id, msession.oid, action="write"):
            logger.warning(f"SECURITY: User {user_id} denied Magellon atlas creation for session: {session_name}")
            raise HTTPException(status_code=403, detail="Access denied to this session")
        try:
            session_id_binary = msession.oid.bytes
        except AttributeError:
            return {"error": "Invalid session ID"}
        # Query to get all atlas-related images for the session
        # This query gets images where parent_id is null (top-level images)
        query = text("""
            SELECT
                i.oid as id,
                i.atlas_dimxy as dimx,
                i.atlas_dimxy as dimy,
                i.name as filename,
                i.atlas_delta_row as delta_row,
                i.atlas_delta_column as delta_column
            FROM image i
            WHERE i.session_id = :session_id
            AND i.atlas_delta_row IS NOT NULL
            AND i.atlas_delta_column IS NOT NULL
            AND i.parent_id IS NULL
            AND i.GCRecord IS NULL
            ORDER BY filename
        """)

        result = db_session.execute(query, {"session_id": session_id_binary})
        atlas_images = result.fetchall()

        if not atlas_images:
            raise HTTPException(status_code=404, detail="No atlas images found for this session")

        # Group images by their grid label prefix use extract_grid_label(row.filename) to get the grid label
        label_objects = {}

        for row in atlas_images:
            # Get the prefix of the filename (everything before the first underscore)
            # filename_parts = row.filename.split('_')
            prefix = extract_grid_label(row.filename) # Using first part as the group identifier

            obj = {
                "id": str(row.id),
                "dimx": float(row.dimx) if row.dimx else 0,
                "dimy": float(row.dimy) if row.dimy else 0,
                "filename": row.filename,
                "delta_row": float(row.delta_row) if row.delta_row else 0,
                "delta_column": float(row.delta_column) if row.delta_column else 0
            }

            if prefix in label_objects:
                label_objects[prefix].append(obj)
            else:
                label_objects[prefix] = [obj]

        # Create atlas images using the existing create_atlas_images function
        images = create_atlas_images(session_name, label_objects)

        # Insert the atlas records into the database
        atlases_to_insert = []
        for image in images:
            file_name = os.path.basename(image['imageFilePath'])
            file_name_without_extension = os.path.splitext(file_name)[0]
            atlas = Atlas(
                oid=uuid.uuid4(),
                name=file_name_without_extension,
                meta=image['imageMap'],
                session_id=msession.oid
            )
            atlases_to_insert.append(atlas)

        db_session.bulk_save_objects(atlases_to_insert)
        db_session.commit()

        logger.info(f"User {user_id} successfully created Magellon atlas for session: {session_name}, {len(images)} images")
        return {"images": images, "created_by": str(user_id)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Magellon atlas for user {user_id}, session {session_name}: {str(e)}")
        db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
