import math
from datetime import datetime
import json
import os
import uuid
from typing import List, Optional, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session
from starlette.responses import FileResponse, JSONResponse

from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, app_settings, THUMBNAILS_SUFFIX, \
    FFT_SUFFIX, CTF_SUB_URL, FAO_SUB_URL
from database import get_db
from lib.image_not_found import get_image_not_found
from models.pydantic_models import SessionDto, ImageDto
from models.sqlalchemy_models import Image, Msession, ImageMetaData, ImageMetaDataCategory
from repositories.image_repository import ImageRepository
from repositories.session_repository import SessionRepository
from services.file_service import FileService
from services.helper import get_response_image
import logging

from core.sqlalchemy_row_level_security import get_session_filter_clause, check_session_access
from dependencies.auth import get_current_user_id

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
        parent_name = db_image.derive_parent_name()
        if parent_name in image_dict:
            db_image.parent_id = image_dict[parent_name]

    db_session.bulk_save_objects(db_image_list)
    db_session.commit()
    logger.info(f"User {user_id} successfully updated parent-child relationships for session: {name}")
    return {'result': "Done!"}




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


