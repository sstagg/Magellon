import asyncio
import math
import mimetypes
from datetime import datetime
import json
import os
import uuid
from io import BytesIO
from operator import truediv
from typing import List, Optional, Dict
from uuid import UUID
import re
import mrcfile
from lxml import etree

import airflow_client.client
import pymysql
from airflow_client.client import ApiClient
from airflow_client.client.api import dag_run_api
from airflow_client.client.model.dag_run import DAGRun

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect

from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, joinedload
from starlette.responses import FileResponse, JSONResponse
from pathlib import Path

from config import FFT_SUB_URL, IMAGE_SUB_URL, MAGELLON_HOME_DIR, THUMBNAILS_SUB_URL, app_settings, THUMBNAILS_SUFFIX, \
    FFT_SUFFIX, ATLAS_SUB_URL, CTF_SUB_URL, FAO_SUB_URL
from core.helper import create_motioncor_task_data, push_task_to_task_queue, dispatch_ctf_task, dispatch_motioncor_task, create_motioncor_task
from core.task_factory import MotioncorTaskFactory

from database import get_db
from lib.image_not_found import get_image_not_found
from models.plugins_models import CryoEmMotionCorTaskData, MOTIONCOR_TASK, PENDING
from models.pydantic_models import SerialEMImportTaskDto, SessionDto, ImageDto, AtlasDto,     ParticlePickingDto
from models.sqlalchemy_models import Image, Msession, ImageMetaData, Atlas, ImageMetaDataCategory
from repositories.image_repository import ImageRepository
from repositories.session_repository import SessionRepository
from services.atlas import create_atlas_images
from services.file_service import FileService
from services.helper import get_response_image, get_parent_name
import logging

# Row-Level Security imports
from core.sqlalchemy_row_level_security import get_session_filter_clause, check_session_access
from dependencies.auth import get_current_user_id


from services.importers.EPUImporter import EPUImporter
from pathlib import Path
# from services.image_file_service import get_images, get_image_by_stack, get_image_data

webapp_router = APIRouter()
file_service = FileService("transfer.log")

logger = logging.getLogger(__name__)
# @webapp_router.get('/images_old')
# def get_images_old_route():
#     return get_images()

# @webapp_router.get('/images_by_stack_old')
# def get_images_by_stack_old_route(ext: str):
#     return get_image_by_stack(ext)
@webapp_router.get('/session_mags')
def get_session_mags(
    session_name: str,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # RLS: Get current user
):
    # session_name = "22apr01a"
    # level = 4

    # Get the Msession based on the session name
    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if msession is None:
        return {"error": "Session not found"}

    # RLS: Check if user has access to this session
    if not check_session_access(user_id, msession.oid, action="read"):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to session '{session_name}'"
        )

    try:
        session_id_binary = msession.oid.bytes
    except AttributeError:
        return {"error": "Invalid session ID"}

    # RLS: Get filter clause for session-level security
    filter_clause, filter_params = get_session_filter_clause(user_id)

    query = text(f"""
        SELECT  image.magnification AS mag
        FROM image
        WHERE image.session_id = :session_id
        {filter_clause}
        GROUP BY image.magnification
        ORDER BY mag  """)
    try:
        # RLS: Merge filter parameters
        params = {"session_id": session_id_binary, **filter_params}
        result = db_session.execute(query, params)
        rows = result.fetchall()
        # Convert rows to a list of dictionaries with named keys
        return [row[0] for row in rows[1:]]
    except Exception as e:
        raise Exception(f"Database query execution error: {str(e)}")


@webapp_router.get('/images')
def get_images_route(
        db_session: Session = Depends(get_db),
        user_id: UUID = Depends(get_current_user_id),  # RLS: Get current user
        session_name: Optional[str] = Query(None),
        parentId: Optional[UUID] = Query(None),
        page: int = Query(1, alias="page", description="Page number", ge=1),
        pageSize: int = Query(10, alias="pageSize", description="Number of results per page", le=1000)
):
    # Get the Msession based on the session name
    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if msession is None:
        return {"error": "Session not found"}

    # RLS: Check if user has access to this session
    if not check_session_access(user_id, msession.oid, action="read"):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to session '{session_name}'"
        )

    try:
        session_id_binary = msession.oid.bytes
    except AttributeError:
        return {"error": "Invalid session ID"}

    # Calculate offset and limit based on page and pageSize
    offset = (page - 1) * pageSize
    limit = pageSize

    try:
        parent_id_binary = parentId.bytes
    except AttributeError:
        parent_id_binary = None

    # RLS: Get filter clause for session-level security
    filter_clause, filter_params = get_session_filter_clause(user_id)

    count_query = text(f"""
         SELECT COUNT(*) FROM image i
            WHERE (:parentId IS NULL
            AND i.parent_id IS NULL
            OR i.parent_id = :parentId)
            AND i.session_id = :sessionId
            {filter_clause};
        """)

    query = text(f"""
        SELECT
          i.oid,
          i.name ,
          i.defocus,
          i.dose,
          i.magnification AS mag,
          i.pixel_size AS pixelSize,
          i.parent_id,
          i.binning_x,
          i.session_id,
           (
            SELECT COUNT(*)
            FROM image c
            WHERE c.parent_id = i.oid
              AND c.session_id = i.session_id
          ) AS children_count
        FROM image i
        WHERE (:parentId IS NULL
        AND i.parent_id IS NULL
        OR i.parent_id = :parentId)
        AND i.session_id = :sessionId
        {filter_clause}
        LIMIT :limit OFFSET :offset;
        """)
    try:
        # RLS: Merge filter parameters
        params = {
            "parentId": parent_id_binary,
            "sessionId": session_id_binary,
            "limit": limit,
            "offset": offset,
            **filter_params
        }
        result = db_session.execute(query, params)
        rows = result.fetchall()
        images_as_dict = []
        for row in rows:
            image = ImageDto(
    oid=row.oid,
    name=row.name,
    defocus=round(float(row.defocus) * 1.e6, 2) if row.defocus is not None else row.defocus,
    dose=row.dose,
    mag=row.mag,
    pixelSize=round(float(row.pixelSize) * row.binning_x * 1.e10, 3)
        if row.pixelSize is not None and row.binning_x is not None else None,    parent_id=row.parent_id,
    session_id=row.session_id,
    children_count=row.children_count
)
            images_as_dict.append(image.dict())

        # total_count = images_as_dict[0]["total_count"] if images_as_dict else 0
        # return {"total_count": total_count, "result": images_as_dict}
        # RLS: Use merged params for count query too
        count_params = {"parentId": parent_id_binary, "sessionId": session_id_binary, **filter_params}
        count_result = db_session.execute(count_query, count_params)
        total_count = count_result.scalar()
        next_page = page + 1 if total_count > page * pageSize else None

        return {
            "total_count": total_count,
            "page": page,
            "pageSize": pageSize,
            "next_page": next_page,
            "result": images_as_dict
        }

    except Exception as e:
        raise Exception(f"Database query execution error: {str(e)}")


@webapp_router.get('/images/{image_name}')
def get_image_route(
        image_name: str,
        db_session: Session = Depends(get_db),
        user_id: UUID = Depends(get_current_user_id)  # RLS: Get current user
):
    try:
        # Assuming the session name is the part of the image name preceding underscore
        session_name = image_name.split('_')[0]

        # Get the Msession based on the session name
        msession = db_session.query(Msession).filter(Msession.name == session_name).first()
        if msession is None:
            raise HTTPException(status_code=404, detail="Session not found")

        # RLS: Check if user has access to this session
        if not check_session_access(user_id, msession.oid, action="read"):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to session '{session_name}'"
            )

        try:
            session_id_binary = msession.oid.bytes
        except AttributeError:
            raise HTTPException(status_code=500, detail="Invalid session ID")

        # RLS: Get filter clause for session-level security
        filter_clause, filter_params = get_session_filter_clause(user_id)

        # Fetch the single image based on the image name
        query = text(f"""
            SELECT
              i.oid,
              i.name,
              i.defocus,
              i.dose,
              i.magnification AS mag,
              i.pixel_size AS pixelSize,
              i.parent_id,
              i.binning_x,
              i.session_id,
               (
                SELECT COUNT(*)
                FROM image c
                WHERE c.parent_id = i.Oid
                  AND c.session_id = i.session_id
              ) AS children_count
            FROM image i
            WHERE i.name = :image_name
              AND i.session_id = :sessionId
              {filter_clause};
            """)
        # RLS: Merge filter parameters
        params = {"image_name": image_name, "sessionId": session_id_binary, **filter_params}
        result = db_session.execute(query, params)
        row = result.fetchone()

        if row is not None:
            image = ImageDto(
                oid=row.oid,
                name=row.name,
                defocus=round(float(row.defocus) * 1.e6, 2),
                dose=row.dose,
                mag=row.mag,
                pixelSize=round(float(row.pixelSize) * row.binning_x * 1.e10, 3),
                parent_id=row.parent_id,
                session_id=row.session_id,
                children_count=row.children_count
            )
            return {"result": image.dict()}

        raise HTTPException(status_code=404, detail="Image not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query execution error: {str(e)}")





@webapp_router.get('/fft_image')
def get_fft_image_route(
    name: str,
    sessionName: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get FFT image file.

    **Requires:** Authentication
    **Security:** User must have access to the session
    """
    if sessionName:
        session_name = sessionName.lower()
    else:
        underscore_index = name.find('_')
        session_name = name[:underscore_index].lower()

    logger.debug(f"User {user_id} requesting FFT image: {name} from session: {session_name}")

    # ✅ Verify session exists and check access
    db_session = next(get_db())
    try:
        msession = db_session.query(Msession).filter(Msession.name == session_name).first()
        if not msession:
            raise HTTPException(status_code=404, detail="Session not found")

        if not check_session_access(user_id, msession.oid, action="read"):
            logger.warning(f"SECURITY: User {user_id} denied FFT image access for session: {session_name}")
            raise HTTPException(status_code=403, detail="Access denied to this session")
    finally:
        db_session.close()

    file_path = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name}/{FFT_SUB_URL}{name}{FFT_SUFFIX}"
    return FileResponse(file_path, media_type='image/png')



# Endpoint to get image metadata
@webapp_router.get("/images/{image_id}/metadata")#, response_model=List[CategoryResponse]
def get_image_metadata(
    image_id: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get metadata for a specific image.

    **Requires:** Authentication
    **Security:** User must have access to the image's session
    """
    logger.debug(f"User {user_id} requesting metadata for image: {image_id}")

    # Fetch the image by its ID (name field in this case)
    db_image = db.query(Image).filter_by(name=image_id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found.")

    # ✅ Check session access
    if db_image.session_id:
        if not check_session_access(user_id, db_image.session_id, action="read"):
            logger.warning(f"SECURITY: User {user_id} denied metadata access to image: {image_id}")
            raise HTTPException(status_code=403, detail="Access denied to this image")

    # Fetch all metadata associated with the image
    metas = db.query(ImageMetaData).filter(ImageMetaData.image_id == db_image.oid).all()

    # Fetch all categories
    categories = db.query(ImageMetaDataCategory).all()


    # Create a mapping of categories by their parent-child relationship
    category_dict = {}
    for category in categories:
        category_dict[category.oid] = {
            "oid": category.oid,
            "name": category.name,
            "parent": category.parent_id,
            "metadata": [],
            "children": []
        }

    # Attach metadata to categories
    for meta in metas:
        # Find the category this metadata belongs to
        if meta.category_id and meta.category_id in category_dict:
            category_dict[meta.category_id]["metadata"].append({
                "oid": meta.oid,
                "name": meta.name,
                "data": meta.data,
                "data_json": meta.data_json
            })
        else:
            # Create an "orphan" category for metadata without a category
            if "orphan" not in category_dict:
                category_dict["orphan"] = {
                    "oid": "orphan",
                    "name": "Orphan Category",
                    "parent": None,
                    "metadata": [],
                    "children": []
                }
            category_dict["orphan"]["metadata"].append({
                "oid": meta.oid,
                "name": meta.name,
                "data": meta.data,
                "data_json": meta.data_json
            })

    # Organize the hierarchy: add children to their parents
    category_hierarchy = []
    for category in category_dict.values():
        if category["parent"] is None:
            # Top-level category
            category_hierarchy.append(category)
        else:
            # Attach to its parent
            if category["parent"] in category_dict:
                category_dict[category["parent"]]["children"].append(category)

    # Return the hierarchical structure
    return category_hierarchy







@webapp_router.get('/ctf-info')
def get_image_ctf_data_route(
    image_name_or_oid: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get CTF (Contrast Transfer Function) data for an image.

    **Requires:** Authentication
    **Security:** User must have access to the image's session
    """
    logger.debug(f"User {user_id} requesting CTF data for image: {image_name_or_oid}")

    try:
        try:
            # Attempt to convert image_name_or_oid to UUID
            image_uuid = UUID(image_name_or_oid)
            # If convertible to UUID, search by OID
            db_image = db.query(Image).filter_by(oid=image_uuid).first()
        except ValueError:
            # If not convertible to UUID, search by filename
            db_image = db.query(Image).filter_by(name=image_name_or_oid).first()

        if not db_image:
            return HTTPException(status_code=404, detail="Image not found")

        # ✅ Check session access
        if db_image.session_id:
            if not check_session_access(user_id, db_image.session_id, action="read"):
                logger.warning(f"SECURITY: User {user_id} denied CTF data access to image: {image_name_or_oid}")
                raise HTTPException(status_code=403, detail="Access denied to this image")

    except NoResultFound:
        return HTTPException(status_code=404, detail="Image not found")

    db_ctf = db.query(ImageMetaData).filter(
        ImageMetaData.image_id == db_image.oid,
        ImageMetaData.data_json != None,
        ImageMetaData.name=="CTF Meta Data"
    ).first()

    # Check if CTF data exists
    if not db_ctf or not db_ctf.data_json:
        raise HTTPException(status_code=404, detail="CTF data not found for this image")

    # data_json format: [{"key": "CTF", "value": {...}}, ...]
    try:
        ctf_entry = next(item for item in db_ctf.data_json if item['key'] == 'CTF')
        ctf_value = ctf_entry['value']

        # If value is a string, it should be a stringified JSON, so we need to parse it
        if isinstance(ctf_value, str):
            ctf_data = json.loads(ctf_value)
        else:
            ctf_data = ctf_value  # If it's already a dictionary, use it directly
    except (KeyError, StopIteration, json.JSONDecodeError) as e:
        logger.error(f"Error parsing CTF data for image {image_path}: {str(e)}")
        raise HTTPException(status_code=500, detail="Invalid CTF data format")


    # Defocus1 and Defocus2: Multiply by 10^6 and add units of μm
    defocus1 = round(float(ctf_data.get('defocus1', 0)) * 1e6, 2) if 'defocus1' in ctf_data else None
    defocus2 = round(float(ctf_data.get('defocus2', 0)) * 1e6, 2) if 'defocus2' in ctf_data else None
    angle_astigmatism = round(math.degrees(float(ctf_data.get('angle_astigmatism', 0))), 2) if 'angle_astigmatism' in ctf_data else None
    resolution = round(float(ctf_data.get('resolution_50_percent', 0)), 2) if 'resolution_50_percent' in ctf_data else None

    result = {
        "filename": db_image.name,
        "defocus1": defocus1,
        "defocus2": defocus2,
        "angleAstigmatism": angle_astigmatism,
        "resolution": resolution
    }


    return result


@webapp_router.get('/ctf_image')
def get_ctf_image_route(
    name: str,
    image_type: str,
    sessionName: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get CTF image file (powerspec or plots).

    **Requires:** Authentication
    **Security:** User must have access to the session
    """
    try:
        if sessionName:
            session_name = sessionName.lower()
        else:
            session_name = name.split('_', 1)[0].lower()  # Use split instead of find

        logger.debug(f"User {user_id} requesting CTF image: {name} type: {image_type} from session: {session_name}")

        # ✅ Verify session exists and check access
        db_session = next(get_db())
        try:
            msession = db_session.query(Msession).filter(Msession.name == session_name).first()
            if not msession:
                raise HTTPException(status_code=404, detail="Session not found")

            if not check_session_access(user_id, msession.oid, action="read"):
                logger.warning(f"SECURITY: User {user_id} denied CTF image access for session: {session_name}")
                raise HTTPException(status_code=403, detail="Access denied to this session")
        finally:
            db_session.close()

        base_path = os.path.join(app_settings.directory_settings.MAGELLON_HOME_DIR, session_name, CTF_SUB_URL, name)
        

        # Define a mapping for file paths based on the image type
        file_paths = {
            "powerspec": f"{base_path}/{name}_ctf_output.mrc-powerspec.jpg",
            "plots": f"{base_path}/{name}_ctf_output.mrc-plots.png"
        }
        logger.debug("file_paths: {}".format(file_paths))

        # Fetch the corresponding file path
        file_path = file_paths.get(image_type)
        if not file_path or not os.path.exists(file_path):
            return get_image_not_found()

        return FileResponse(file_path, media_type='image/png')

    except Exception as e:
        # Add logging if needed, and return an appropriate error response
        print(f"Error fetching CTF image: {e}")
        return get_image_not_found()
@webapp_router.get('/fao_image')
def get_fao_image_route(
    name: str,
    image_type: str,
    sessionName: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get FAO (Focus Area Overview) image file.

    **Requires:** Authentication
    **Security:** User must have access to the session
    """
    try:
        if sessionName:
            session_name = sessionName.lower()
        else:
            session_name = name.split('_', 1)[0].lower()  # Use split instead of find

        logger.debug(f"User {user_id} requesting FAO image: {name} type: {image_type} from session: {session_name}")

        # ✅ Verify session exists and check access
        db_session = next(get_db())
        try:
            msession = db_session.query(Msession).filter(Msession.name == session_name).first()
            if not msession:
                raise HTTPException(status_code=404, detail="Session not found")

            if not check_session_access(user_id, msession.oid, action="read"):
                logger.warning(f"SECURITY: User {user_id} denied FAO image access for session: {session_name}")
                raise HTTPException(status_code=403, detail="Access denied to this session")
        finally:
            db_session.close()

        base_path = os.path.join(app_settings.directory_settings.MAGELLON_HOME_DIR, session_name, FAO_SUB_URL, name)


        # Define a mapping for file paths based on the image type
        file_paths = {
            "one": f"{base_path}/{name}_mco_one.jpg",
            "two": f"{base_path}/{name}_mco_two.jpg"
        }
        logger.debug("file_paths: {}".format(file_paths))

        # Fetch the corresponding file path
        file_path = file_paths.get(image_type)
        if not file_path or not os.path.exists(file_path):
            return get_image_not_found()

        return FileResponse(file_path, media_type='image/png')

    except Exception as e:
        # Add logging if needed, and return an appropriate error response
        print(f"Error fetching CTF image: {e}")
        return get_image_not_found()


@webapp_router.get('/image_info')
def get_image_data_route(
    name: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get image metadata (defocus, pixel size, magnification, dose).

    **Requires:** Authentication
    **Security:** User must have access to the image's session
    """
    logger.debug(f"User {user_id} requesting image info for: {name}")

    db_image = ImageRepository.fetch_by_name(db, name)
    if db_image is None:
        raise HTTPException(status_code=404, detail="image not found with the given name")

    # ✅ Check session access
    if db_image.session_id:
        if not check_session_access(user_id, db_image.session_id, action="read"):
            logger.warning(f"SECURITY: User {user_id} denied image info access to: {name}")
            raise HTTPException(status_code=403, detail="Access denied to this image")

    result = {
        "filename": db_image.name,
        "defocus": round(float(db_image.defocus) * 1.e6, 2),
        "PixelSize": round(float(db_image.pixel_size) * db_image.binning_x * 1.e10, 3),
        "mag": db_image.magnification,
        "dose": round(db_image.dose, 2) if db_image.dose is not None else "none",
    }
    return {'result': result}




@webapp_router.get('/parent_child')
def get_correct_image_parent_child(
    name: str,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Update parent-child relationships for images in a session.

    **Requires:** Authentication
    **Security:** User must have write access to the session
    """
    logger.info(f"User {user_id} updating parent-child relationships for session: {name}")

    # ✅ Verify session exists and check access
    msession = db_session.query(Msession).filter(Msession.name == name).first()
    if not msession:
        raise HTTPException(status_code=404, detail="Session not found")

    if not check_session_access(user_id, msession.oid, action="write"):
        logger.warning(f"SECURITY: User {user_id} denied parent-child update for session: {name}")
        raise HTTPException(status_code=403, detail="Access denied to this session")

    db_image_list = ImageRepository.fetch_all_by_session_name(db_session, name)
    if not db_image_list:
        raise HTTPException(status_code=404, detail="images not found with the given name")
    image_dict = {}
    image_dict = {db_image.name: db_image.oid for db_image in db_image_list}

    for db_image in db_image_list:
        parent_name = get_parent_name(db_image.name)
        if parent_name in image_dict:
            db_image.parent_id = image_dict[parent_name]

    db_session.bulk_save_objects(db_image_list)
    db_session.commit()
    logger.info(f"User {user_id} successfully updated parent-child relationships for session: {name}")
    return {'result': "Done!"}


@webapp_router.post("/particle-pickings", summary="creates particle picking metadata for a given image and returns it",
                    status_code=201)
async def create_particle_picking(
    meta_name: str = Query(...),
    image_name_or_oid: str = Query(...),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Create particle picking metadata for an image.

    **Requires:** Authentication
    **Security:** User must have write access to the image's session
    """
    logger.info(f"User {user_id} creating particle picking metadata: {meta_name} for image: {image_name_or_oid}")

    try:
        try:
            # Attempt to convert image_name_or_oid to UUID
            image_uuid = UUID(image_name_or_oid)
            # If convertible to UUID, search by OID
            image = db.query(Image).filter_by(oid=image_uuid).first()
        except ValueError:
            # If not convertible to UUID, search by filename
            image = db.query(Image).filter_by(name=image_name_or_oid).first()

        if not image:
            return HTTPException(status_code=404, detail="Image not found")

        # ✅ Check session access
        if image.session_id:
            if not check_session_access(user_id, image.session_id, action="write"):
                logger.warning(f"SECURITY: User {user_id} denied particle picking creation for image: {image_name_or_oid}")
                raise HTTPException(status_code=403, detail="Access denied to this image")

    except NoResultFound:
        # db.close()
        return HTTPException(status_code=404, detail="Image not found")

    try:
        # Check if a "manual" Particlepickingjob already exists
        image_meta_data = db.query(ImageMetaData).filter_by(name=meta_name).one()
    except NoResultFound:
        # If it doesn't exist, create a new one
        image_meta_data = ImageMetaData(

            oid=uuid.uuid4(),
            name=meta_name,
            # description="manual job for particle picking",
            created_date=datetime.now(),
            image_id=image.oid,
            type=5
            # msession=image.msession if image.msession is not None else None,
            # Add other necessary fields here
        )
        # if image.msession is not None:
        #     # Include the image's session in the job and item
        #     manual_job.msession = image.msession
        db.add(image_meta_data)
        db.commit()
        db.refresh(image_meta_data)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@webapp_router.get('/particle-pickings')
def get_image_particles(
    img_name: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get particle picking metadata for an image.

    **Requires:** Authentication
    **Security:** User must have access to the image's session
    """
    logger.debug(f"User {user_id} requesting particle pickings for image: {img_name}")

    # ✅ First check if user has access to this image's session
    db_image = db.query(Image).filter(Image.name == img_name).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    if db_image.session_id:
        if not check_session_access(user_id, db_image.session_id, action="read"):
            logger.warning(f"SECURITY: User {user_id} denied particle pickings access to image: {img_name}")
            raise HTTPException(status_code=403, detail="Access denied to this image")

    result = db.query(ImageMetaData). \
        join(Image, ImageMetaData.image_id == Image.oid). \
        filter(Image.name == img_name). \
        all()
    if not result:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitems found for Image")
    response = []
    for row in result:
        image_meta_data = row
        response.append(ParticlePickingDto(
            oid=image_meta_data.oid,
            name=image_meta_data.name,
            image_id=image_meta_data.image_id,
            data_json=json.dumps(image_meta_data.data_json),
            # status=particlepickingjobitem.status,
            # type=particlepickingjobitem.type
        ))
    return response




@webapp_router.get('/particles/{oid}', summary="gets an image particles json by its unique id")
async def get_image_particle_by_id(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get particle picking data by metadata OID.

    **Requires:** Authentication
    **Security:** User must have access to the image's session
    """
    logger.debug(f"User {user_id} requesting particle by OID: {oid}")

    ppji = db.query(ImageMetaData).filter(ImageMetaData.Oid == oid).all()
    if not ppji:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitem found for Image")

    # ✅ Check session access via the image
    metadata = ppji[0]
    if metadata.image_id:
        db_image = db.query(Image).filter(Image.oid == metadata.image_id).first()
        if db_image and db_image.session_id:
            if not check_session_access(user_id, db_image.session_id, action="read"):
                logger.warning(f"SECURITY: User {user_id} denied particle access for OID: {oid}")
                raise HTTPException(status_code=403, detail="Access denied to this particle data")

    return metadata.data


@webapp_router.put("/particle-pickings", summary="Update particle picking data")
async def update_particle_picking(
    body_req: ParticlePickingDto,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Update particle picking data.

    **Requires:** Authentication
    **Security:** User must have write access to the image's session
    """
    logger.info(f"User {user_id} updating particle picking: {body_req.oid}")

    try:
        image_meta_data = db_session.query(ImageMetaData).filter(ImageMetaData.oid == body_req.oid).first()
        if not image_meta_data:
            raise HTTPException(status_code=404, detail="Particle picking  not found")

        # ✅ Check session access via the image
        if image_meta_data.image_id:
            db_image = db_session.query(Image).filter(Image.oid == image_meta_data.image_id).first()
            if db_image and db_image.session_id:
                if not check_session_access(user_id, db_image.session_id, action="write"):
                    logger.warning(f"SECURITY: User {user_id} denied particle picking update for OID: {body_req.oid}")
                    raise HTTPException(status_code=403, detail="Access denied to update this particle data")

        if body_req.data:
            image_meta_data.data_json = json.loads(body_req.data)

        # db_session.merge(body_req)
        db_session.commit()
        db_session.refresh(image_meta_data)
        logger.info(f"User {user_id} successfully updated particle picking: {body_req.oid}")
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating Particle picking : {str(e)}")
    return image_meta_data


@webapp_router.get("/debug/casbin-check")
async def debug_casbin_check(
    session_name: str,
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Debug endpoint to check Casbin configuration and access.

    **Requires:** Authentication
    """
    from services.casbin_service import CasbinService

    # Force reload policies
    enforcer = CasbinService.get_enforcer()
    enforcer.load_policy()

    # Get session
    db_session = next(get_db())
    try:
        msession = db_session.query(Msession).filter(Msession.name == session_name.lower()).first()
        if not msession:
            return {"error": "Session not found"}

        # Check access
        resource = f"msession:{msession.oid}"
        access_result = CasbinService.enforce(str(user_id), resource, "read")

        # Get user roles
        roles = enforcer.get_roles_for_user(str(user_id))

        # Get relevant policies
        admin_policies = enforcer.get_filtered_policy(0, "Administrator")
        msession_policies = [p for p in admin_policies if "msession" in p[1]]

        return {
            "user_id": str(user_id),
            "session_name": session_name,
            "session_oid": str(msession.oid),
            "resource": resource,
            "access_granted": access_result,
            "user_roles": roles,
            "administrator_msession_policies": msession_policies,
            "model_path": "configs/casbin_model.conf"
        }
    finally:
        db_session.close()


@webapp_router.get("/image_thumbnail")
async def get_image_thumbnail(
    name: str,
    sessionName: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get image thumbnail file.

    **Requires:** Authentication
    **Security:** User must have access to the session
    """
    if sessionName:
        session_name = sessionName.lower()
    else:
        underscore_index = name.find('_')
        session_name = name[:underscore_index].lower()

    logger.info(f"[THUMBNAIL] User {user_id} requesting thumbnail: {name} from session: {session_name}")

    # ✅ Verify session exists and check access
    db_session = next(get_db())
    try:
        msession = db_session.query(Msession).filter(Msession.name == session_name).first()
        if not msession:
            logger.error(f"[THUMBNAIL] Session not found: {session_name}")
            raise HTTPException(status_code=404, detail="Session not found")

        logger.info(f"[THUMBNAIL] Found session {session_name}, OID: {msession.oid}")

        access_granted = check_session_access(user_id, msession.oid, action="read")
        logger.info(f"[THUMBNAIL] Access check result for user {user_id} on session {msession.oid}: {access_granted}")

        if not access_granted:
            logger.warning(f"[THUMBNAIL] SECURITY: User {user_id} denied thumbnail access for session: {session_name} (OID: {msession.oid})")
            raise HTTPException(status_code=403, detail="Access denied to this session")

        logger.info(f"[THUMBNAIL] Access granted, serving file: {name}")
    finally:
        db_session.close()

    file_path = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name}/{IMAGE_SUB_URL}{name}.png"

    # Check if the file exists
    if not os.path.exists(file_path):
        return get_image_not_found()

    return FileResponse(file_path, media_type='image/png')


@webapp_router.get("/atlases", response_model=List[AtlasDto])
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


@webapp_router.get("/atlas-image")
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


@webapp_router.get("/image_thumbnail_url")
async def get_image_thumbnail_url(
    name: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get the thumbnail URL for an image.

    **Requires:** Authentication
    **Security:** Authenticated users can get thumbnail URLs
    **Note:** This exposes filesystem paths - use with caution
    """
    logger.debug(f"User {user_id} requesting thumbnail URL for image: {name}")
    return f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{IMAGE_SUB_URL}{name}.png"

@webapp_router.get('/sessions', response_model=List[SessionDto])
def get_all_sessions(
    name: Optional[str] = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get all the sessions in database.

    **Requires:** Authentication
    **Security:** Users can only see sessions they have access to (RLS enforced)
    """
    logger.debug(f"User {user_id} fetching sessions")

    if name:
        sessions = []
        db_msession = SessionRepository.fetch_by_name(db, name)

        # Check if user has access to this specific session
        if db_msession and check_session_access(user_id, db_msession.oid, action="read"):
            sessions.append(db_msession)
            logger.debug(f"User {user_id} accessed session: {name}")
        else:
            logger.warning(f"SECURITY: User {user_id} denied access to session: {name}")

        return sessions
    else:
        # Fetch all sessions and filter by access
        all_sessions = SessionRepository.fetch_all(db)

        # Filter sessions based on user access
        accessible_sessions = []
        for session in all_sessions:
            if check_session_access(user_id, session.oid, action="read"):
                accessible_sessions.append(session)

        logger.debug(f"User {user_id} fetched {len(accessible_sessions)} accessible sessions (out of {len(all_sessions)} total)")
        return accessible_sessions


# @webapp_router.post("/run_dag")
# async def run_dag():
#     try:
#         # post 'http://128.186.103.43:8383/api/v1/dags/my_dag/dagRuns'
#         configuration = airflow_client.client.Configuration(
#             host="http://128.186.103.43:8383/api/v1",
#
#             username='admin',
#             password='admin'
#         )
#         configuration.verify_ssl = False
#         DAG_ID = "my_dag"
#         # Enter a context with an instance of the API client
#         api_client = ApiClient(configuration)
#
#         errors = False
#
#         print('[blue]Triggering a DAG run')
#         dag_run_api_instance = dag_run_api.DAGRunApi(api_client)
#         try:
#             # Create a DAGRun object (no dag_id should be specified because it is read-only property of DAGRun)
#             # dag_run id is generated randomly to allow multiple executions of the script
#             dag_run = DAGRun(
#                 dag_run_id='some_test_run_' + uuid.uuid4().hex,
#             )
#             api_response = dag_run_api_instance.post_dag_run(DAG_ID, dag_run)
#             print(api_response)
#         except airflow_client.client.exceptions.OpenApiException as e:
#             print("[red]Exception when calling DAGRunAPI->post_dag_run: %s\n" % e)
#             errors = True
#         else:
#             print('[green]Posting DAG Run successful')
#
#
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     else:
#         return {"message": "Files transferred successfully."}


@webapp_router.get("/create_atlas")
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

@webapp_router.get("/create_magellon_atlas")
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




@webapp_router.get('/do_ctf')
async def get_do_image_ctf_route(
    full_image_path: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Dispatch a CTF (Contrast Transfer Function) processing task.

    **Requires:** Authentication
    **Security:** Authenticated users can trigger CTF processing
    **Note:** This is a CPU-intensive operation
    """
    logger.info(f"User {user_id} dispatching CTF task for image: {full_image_path}")

    # full_image_path="/gpfs/research/stagg/leginondata/23oct13x/rawdata/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"
    # session_name = "23oct13x"
    # file_name = "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex"

    # Extract file name without extension
    result = await dispatch_ctf_task(uuid.uuid4(), full_image_path)
    logger.info(f"User {user_id} successfully dispatched CTF task for: {full_image_path}")
    return result






class DirectoryNode(BaseModel):
    id: str
    label: str
    abs_path: str  # Absolute path for each directory or file
    children: Optional[List["DirectoryNode"]] = None

def get_directory_structure(root_path: str) -> List[DirectoryNode]:
    if not os.path.isdir(root_path):
        raise HTTPException(status_code=400, detail="Invalid root directory path")

    def build_tree(path: str) -> DirectoryNode:
        label = os.path.basename(path) or path  # Root may not have a basename

        node_id = str(uuid.uuid4())  # Unique ID for each node
        children = []

        try:
            for entry in os.scandir(path):
                if entry.is_dir():
                    children.append(build_tree(entry.path))
                elif entry.is_file() and (entry.name.endswith('.mrc') or entry.name.endswith('.tiff')):
                    # Including the absolute path for each file
                    children.append(DirectoryNode(id=str(uuid.uuid4()), label=entry.name, abs_path=entry.path))
        except PermissionError:
            pass  # Skip directories/files that can't be accessed

        # Return node with the absolute path
        return DirectoryNode(id=node_id, label=label, abs_path=path, children=children or None)

    return [build_tree(root_path)]




# @webapp_router.get("/directory-tree", response_model=List[DirectoryNode])
# def directory_tree(root_path: str):
#     root_path=r"C:\temp\test"
#     return get_directory_structure(root_path)



class ImageResponse(BaseModel):
    images: List[List[List[float]]]
    total_images: int
    height: int
    width: int

class MetadataResponse(BaseModel):
    metadata: Dict[str, List[int]]



def read_images_from_mrc(file_path: str, start_idx: int, count: int) -> ImageResponse:
    """Read a subset of images from an MRC file."""
    try:
        with mrcfile.mmap(file_path, mode='r', permissive=True) as mrc:
            data = mrc.data
            total_images = data.shape[0]

            # Validate indices
            if start_idx >= total_images:
                raise HTTPException(status_code=400, message="Start index out of range")

            end_idx = min(start_idx + count, total_images)
            subset = data[start_idx:end_idx]

            # Normalize the data
            data_min = subset.min()
            data_max = subset.max()
            normalized_data = ((subset - data_min) / (data_max - data_min) * 255).tolist()

            return ImageResponse(
                images=normalized_data,
                total_images=total_images,
                height=data.shape[1],
                width=data.shape[2]
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@webapp_router.get("/mrc/")
async def get_images(
    file_path: str,
    start_idx: int = 0,
    count: int = 10,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
) -> ImageResponse:
    """
    Get a subset of images from an MRC file.

    **Requires:** Authentication
    **Security:** Authenticated users can read MRC files
    **Note:** This allows direct file system access
    """
    logger.debug(f"User {user_id} reading MRC file: {file_path} (start: {start_idx}, count: {count})")
    return read_images_from_mrc(file_path, start_idx, count)



class FileItem(BaseModel):
    id: int
    name: str = Field(..., description="The name of the file or folder")
    is_directory: bool = Field(..., description="True if the item is a folder, False if it's a file")
    path: str = Field(..., description="The full path of the item")
    parent_id: Optional[int] = Field(None, description="The ID of the parent folder")
    size: Optional[int] = Field(None, description="The size of the file in bytes (only for files)")
    mime_type: Optional[str] = Field(None, description="The MIME type of the file (only for files)")
    created_at: datetime
    updated_at: datetime

@webapp_router.get("/files/browse", response_model=List[FileItem])
async def browse_directory(
    path: str = "/gpfs",
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Browse filesystem directories.

    **Requires:** Authentication
    **Security:** Authenticated users can browse the filesystem
    **WARNING:** This exposes filesystem structure and file metadata
    """
    logger.warning(f"SECURITY: User {user_id} browsing filesystem path: {path}")

    try:
        development = False
        if development and path.startswith("/gpfs"):
            path = path.replace("/gpfs", "C:/magellon/gpfs", 1)

        directory = Path(path)
        if not directory.exists():
            raise HTTPException(status_code=404, detail="Directory not found")

        items = []
        for item in directory.iterdir():
            stat = item.stat()
            file_item = FileItem(
                id=hash(str(item)),  # Generate a unique ID based on path hash
                name=item.name,
                is_directory=item.is_dir(),
                path=str(item),
                parent_id=hash(str(item.parent).replace("C:/magellon/gpfs", "/gpfs", 1) if development else str(item.parent)) if str(item.parent) != path else None,
                size=stat.st_size if not item.is_dir() else None,
                mime_type=mimetypes.guess_type(item.name)[0] if not item.is_dir() else None,
                created_at=datetime.fromtimestamp(stat.st_ctime),
                updated_at=datetime.fromtimestamp(stat.st_mtime)
            )
            items.append(file_item)

        # Sort: directories first, then files
        items.sort(key=lambda x: (not x.is_directory, x.name))

        logger.debug(f"User {user_id} retrieved {len(items)} items from path: {path}")
        return items
    except Exception as e:
        logger.error(f"Error browsing directory for user {user_id}, path: {path}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@webapp_router.post("/test-motioncor")
async def test_motioncor(
        image_file: UploadFile = File(...),
        gain_file: UploadFile = File(...),
        defects_path: Optional[str] = Form(None),   
        data: str = Form(...),  # JSON string
        session_name: str = Form("testing"),
        user_id: UUID = Depends(get_current_user_id)
):
    """
    Test motioncor task with uploaded image, gain, and config data.
    
    Sends task to motioncor test queue for processing.
    Returns immediately with task_id for WebSocket subscription.
    
    **Requires:** Authentication
    **Returns:** {status, task_id} - Client uses task_id to connect to WebSocket for updates
    """
    from services.motioncor_test_service import MotioncorTestTaskManager
    
    logger.warning(f"SECURITY: User {user_id} triggering test motioncor for session: {session_name}")
    
    task_id = uuid.uuid4()
    
    try:
        # Parse JSON parameters
        params: dict = json.loads(data)
        base_tmp_dir = Path("/gpfs/tmp")
        base_tmp_dir.mkdir(parents=True, exist_ok=True)

        # Save uploaded files
        image_path = base_tmp_dir / image_file.filename
        gain_path = base_tmp_dir / gain_file.filename
 
        with open(image_path, "wb") as f:
            f.write(await image_file.read())

        with open(gain_path, "wb") as f:
            f.write(await gain_file.read())
        
        # Extract params from form data (params contains the actual form parameters directly)
        params.setdefault("magellon_project_name", "test_project")
        params.setdefault("magellon_session_name", session_name)
        
        # Log the incoming params for debugging
        logger.info(f"Received params: {params}")
        
        # Prepare motioncor settings with frontend parameters
        # Map frontend parameter names to backend parameter names
        motioncor_settings = {}
        
        param_mappings = {
            'FmDose': (float, 'FmDose'),
            'PixSize': (float, 'PixSize'),
            'kV': (float, 'kV'),
            'Patchrows': (int, 'PatchesX'),  # Frontend sends Patchrows -> backend uses PatchesX
            'Patchcols': (int, 'PatchesY'),  # Frontend sends Patchcols -> backend uses PatchesY
            'PatchesX': (int, 'PatchesX'),   # Also support direct PatchesX
            'PatchesY': (int, 'PatchesY'),   # Also support direct PatchesY
            'Group': (int, 'Group'),
            'FtBin': (float, 'FtBin'),
            'Iter': (int, 'Iter'),
            'Tol': (float, 'Tol'),
            'FlipGain': (int, 'FlipGain'),
            'RotGain': (int, 'RotGain'),
            'Bft_global': (int, 'Bft_global'),
            'Bft_local': (int, 'Bft_local')
        }
        
        for frontend_param, (param_type, backend_param) in param_mappings.items():
            if frontend_param in params and params[frontend_param] is not None:
                try:
                    motioncor_settings[backend_param] = param_type(params[frontend_param])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid value for {frontend_param}: {params[frontend_param]}, skipping")
        
        logger.info(f"Built motioncor_settings: {motioncor_settings}")
        
        # Create the test task
        motioncor_task = MotioncorTestTaskManager.create_test_task(
            task_id=task_id,
            image_path=str(image_path),
            gain_path=str(gain_path),
            defects_path=defects_path,
            session_name=session_name,
            task_params=params,
            motioncor_settings=motioncor_settings
        )
        
        # Publish task to the test input queue
        if MotioncorTestTaskManager.publish_task_to_queue(motioncor_task):
            logger.info(f"Motioncor test task {task_id} queued successfully for user {user_id}")
            
            return {
                "status": "queued",
                "task_id": str(task_id),
                "message": "Task has been queued for processing. Connect to WebSocket with this task_id to receive updates.",
                "websocket_url": f"/ws/motioncor-test/{task_id}"
            }
        else:
            logger.error(f"Failed to queue motioncor test task {task_id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to queue task. Please try again."
            )

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in test_motioncor data: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON in request data")
    except Exception as e:
        logger.error(f"Error in test_motioncor endpoint for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@webapp_router.get("/download-motioncor-output/{task_id}/{filename}")
async def download_motioncor_output(
    task_id: str,
    filename: str,
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Download motioncor output files (_DW.mrc or _DWS.mrc file only)
    
    **Requires:** Authentication
    **Returns:** File download
    """
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    logger.warning(f"SECURITY: User {user_id} downloading motioncor output: {filename}")
    
    try:
        # Construct the file path - files are stored in /jobs/{task_id}/
        file_path = os.path.join(app_settings.jobs_dir, task_id, filename)
        
        # Security: Ensure the file path is within the jobs directory
        file_path = os.path.abspath(file_path)
        jobs_dir = os.path.abspath(app_settings.jobs_dir)
        
        if not file_path.startswith(jobs_dir):
            logger.error(f"Security: Attempted to access file outside jobs directory: {file_path}")
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Security: Only allow downloading _DW.mrc or _DWS.mrc files
        if not (filename.endswith("_DW.mrc") or filename.endswith("_DWS.mrc")):
            logger.error(f"Security: Attempted to download non-DW file: {filename}")
            raise HTTPException(status_code=403, detail="Only DW/DWS files can be downloaded")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        logger.info(f"Serving file for download: {file_path}")
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading motioncor output for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

def create_task(session_name="24mar28a", file_name="20241203_54449_integrated_movie",gain_path = "/gpfs/20241202_53597_gain_multi_ref.tif"):
    """
    Creates a motioncor task with specified session name and file name

    Args:
        session_name (str): Name of the session, defaults to "24mar28a"
        file_name (str): Base name of the file, defaults to "20241203_54449_integrated_movie"

    Returns:
        MotioncorTask: Created task object or False if error occurs
    """

    try:
        # Construct the full image path
        image_path = f"/gpfs/{file_name}.mrc.tif"

        # Use the consolidated create_motioncor_task function
        motioncor_task = create_motioncor_task(
            image_path=image_path,
            gain_path=gain_path,
            session_name=session_name,
            task_id=str(uuid.uuid4()),  # Generate new UUID for task
            job_id=uuid.uuid4()  # Generate new UUID for job
        )

        return motioncor_task

    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False


@webapp_router.websocket("/ws/motioncor-test/{task_id}")
async def websocket_motioncor_test(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time motioncor test task updates.
    
    Clients connect to this endpoint using the task_id returned from /test-motioncor.
    Receives status updates and final results as they become available.
    
    **Requires:** Authentication token via query parameter
    **Usage:** 
        - Connect to: ws://host/ws/motioncor-test/{task_id}?token=<your_jwt_token>
        - Receive messages with: type (status_update/result/error), status, and data
    """
    from services.motioncor_test_service import (
        register_websocket_connection, 
        unregister_websocket_connection
    )
    from jose import JWTError, jwt
    from uuid import UUID
    
    logger.info(f"WebSocket connection attempt for task {task_id}")
    
    # CRITICAL: Accept the WebSocket connection IMMEDIATELY
    # This must happen before any other WebSocket operations
    try:
        await websocket.accept()
        logger.debug(f"WebSocket accepted for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to accept WebSocket for task {task_id}: {e}")
        return
    
    # NOW authenticate after accepting
    user_id = None
    
    # Get token from query parameters
    token = websocket.query_params.get("token")
    
    logger.debug(f"Token present: {bool(token)}")
    
    # If we have a token, validate it
    if token:
        try:
            # Manually decode JWT token to avoid HTTPException
            SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-CHANGE-THIS-IN-PRODUCTION-min-32-chars")
            ALGORITHM = "HS256"
            
            logger.debug(f"Decoding JWT token for task {task_id}")
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id_str = payload.get("sub")
            
            if not user_id_str:
                logger.warning(f"WebSocket auth failed for task {task_id}: No user ID in token")
                await websocket.send_json({
                    "type": "error",
                    "error": "Unauthorized - no user ID in token"
                })
                await websocket.close(code=1008, reason="Unauthorized - no user ID")
                return
            
            # Convert to UUID
            try:
                user_id = UUID(user_id_str)
                logger.info(f"User {user_id} authenticated for WebSocket task {task_id}")
            except (ValueError, TypeError):
                logger.warning(f"WebSocket auth failed for task {task_id}: Invalid user ID format")
                await websocket.send_json({
                    "type": "error",
                    "error": "Unauthorized - invalid user format"
                })
                await websocket.close(code=1008, reason="Unauthorized - invalid user format")
                return
                
        except jwt.ExpiredSignatureError:
            logger.warning(f"WebSocket auth failed for task {task_id}: Token expired")
            await websocket.send_json({
                "type": "error",
                "error": "Unauthorized - token expired"
            })
            await websocket.close(code=1008, reason="Unauthorized - token expired")
            return
        except JWTError as e:
            logger.warning(f"WebSocket auth failed for task {task_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Unauthorized - invalid token: {str(e)}"
            })
            await websocket.close(code=1008, reason="Unauthorized - invalid token")
            return
        except Exception as e:
            logger.warning(f"WebSocket auth error for task {task_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "error": f"Unauthorized - auth error: {str(e)}"
            })
            await websocket.close(code=1008, reason="Unauthorized")
            return
    else:
        # No token provided, reject connection
        logger.warning(f"WebSocket connection attempted without token for task {task_id}")
        await websocket.send_json({
            "type": "error",
            "error": "Unauthorized - token required"
        })
        await websocket.close(code=1008, reason="Unauthorized - token required")
        return
    
    # Register the WebSocket connection after authentication
    try:
        connection = await register_websocket_connection(task_id, websocket)
        # Mark the connection as accepted since we already called websocket.accept() above
        connection.is_connected = True
        logger.info(f"WebSocket registered for task {task_id}, user {user_id}")
    except Exception as e:
        logger.error(f"Failed to register WebSocket for task {task_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "error": f"Failed to register connection: {str(e)}"
            })
            await websocket.close(code=1011, reason="Internal error")
        except:
            pass
        return
    
    # Send initial connection message
    try:
        await connection.send_json({
            "type": "connected",
            "task_id": task_id,
            "user_id": str(user_id),
            "message": "Connected to task updates. Waiting for task results..."
        })
        logger.debug(f"Sent connected message for task {task_id}")
    except Exception as e:
        logger.error(f"Failed to send initial message for task {task_id}: {e}")
    
    try:
        # Keep connection alive and listen for client messages
        while True:
            # Wait for any message from client (mainly for keep-alive)
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                logger.debug(f"Received message from client for task {task_id}: {data}")
            except asyncio.TimeoutError:
                # Send keep-alive ping
                try:
                    await connection.send_json({
                        "type": "ping",
                        "task_id": task_id,
                        "message": "Connection alive"
                    })
                except Exception as e:
                    logger.debug(f"Error sending ping for task {task_id}: {e}")
            except json.JSONDecodeError:
                # Client sent invalid JSON, but keep connection open
                logger.warning(f"Invalid JSON received from client for task {task_id}")
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket for task {task_id}")
        try:
            await unregister_websocket_connection(task_id, connection)
        except Exception as e:
            logger.error(f"Error unregistering connection for task {task_id}: {e}")
    except Exception as e:
        logger.error(f"Error in WebSocket connection for task {task_id}: {e}")
        try:
            await unregister_websocket_connection(task_id, connection)
        except:
            pass