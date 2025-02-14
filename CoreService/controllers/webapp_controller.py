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

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, joinedload
from starlette.responses import FileResponse, JSONResponse

from config import FFT_SUB_URL, IMAGE_SUB_URL, MAGELLON_HOME_DIR, THUMBNAILS_SUB_URL, app_settings, THUMBNAILS_SUFFIX, \
    FFT_SUFFIX, ATLAS_SUB_URL, CTF_SUB_URL, FAO_SUB_URL
from core.helper import push_task_to_task_queue, dispatch_ctf_task, dispatch_motioncor_task, create_motioncor_task
from core.task_factory import MotioncorTaskFactory

from database import get_db
from lib.image_not_found import get_image_not_found
from models.plugins_models import CryoEmMotionCorTaskData, MOTIONCOR_TASK, PENDING
from models.pydantic_models import SessionDto, ImageDto, AtlasDto,     ParticlePickingDto
from models.sqlalchemy_models import Image, Msession, ImageMetaData, Atlas, ImageMetaDataCategory
from repositories.image_repository import ImageRepository
from repositories.session_repository import SessionRepository
from services.atlas import create_atlas_images
from services.file_service import FileService
from services.helper import get_response_image, get_parent_name
import logging


from services.importers.EPUImporter import EPUImporter, scan_directory
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
def get_session_mags(session_name: str, db_session: Session = Depends(get_db)):
    # session_name = "22apr01a"
    # level = 4

    # Get the Msession based on the session name
    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if msession is None:
        return {"error": "Session not found"}
    try:
        session_id_binary = msession.oid.bytes
    except AttributeError:
        return {"error": "Invalid session ID"}

    query = text("""
        SELECT  image.magnification AS mag
        FROM image
        WHERE image.session_id = :session_id
        GROUP BY image.magnification
        ORDER BY mag  """)
    try:
        # result = db_session.execute(query) if params is None else db_session.execute(query, params)
        result = db_session.execute(query, {"session_id": session_id_binary})
        rows = result.fetchall()
        # Convert rows to a list of dictionaries with named keys
        return [row[0] for row in rows[1:]]
    except Exception as e:
        raise Exception(f"Database query execution error: {str(e)}")


@webapp_router.get('/images')
def get_images_route(
        db_session: Session = Depends(get_db),
        session_name: Optional[str] = Query(None),
        parentId: Optional[UUID] = Query(None),
        page: int = Query(1, alias="page", description="Page number", ge=1),
        pageSize: int = Query(10, alias="pageSize", description="Number of results per page", le=1000)
):
    # Get the Msession based on the session name
    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if msession is None:
        return {"error": "Session not found"}
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

    count_query = text("""
         SELECT COUNT(*) FROM image i
            WHERE (:parentId IS NULL
            AND i.parent_id IS NULL
            OR i.parent_id = :parentId)
            AND i.session_id = :sessionId;
        """)

    query = text("""
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
        LIMIT :limit OFFSET :offset;
        """)
    try:
        result = db_session.execute(
            query,
            {"parentId": parent_id_binary, "sessionId": session_id_binary, "limit": limit, "offset": offset}
        )
        rows = result.fetchall()
        images_as_dict = []
        for row in rows:
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
            images_as_dict.append(image.dict())

        # total_count = images_as_dict[0]["total_count"] if images_as_dict else 0
        # return {"total_count": total_count, "result": images_as_dict}
        count_result = db_session.execute(count_query, {"parentId": parent_id_binary, "sessionId": session_id_binary})
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
        db_session: Session = Depends(get_db)
):
    try:
        # Assuming the session name is the part of the image name preceding underscore
        session_name = image_name.split('_')[0]

        # Get the Msession based on the session name
        msession = db_session.query(Msession).filter(Msession.name == session_name).first()
        if msession is None:
            raise HTTPException(status_code=404, detail="Session not found")

        try:
            session_id_binary = msession.oid.bytes
        except AttributeError:
            raise HTTPException(status_code=500, detail="Invalid session ID")

        # Fetch the single image based on the image name
        query = text("""
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
              AND i.session_id = :sessionId;
            """)
        result = db_session.execute(
            query,
            {"image_name": image_name, "sessionId": session_id_binary}
        )
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
def get_fft_image_route(name: str):
    underscore_index = name.find('_')
    session_name = name[:underscore_index]
    file_path = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name}/{FFT_SUB_URL}{name}{FFT_SUFFIX}"
    return FileResponse(file_path, media_type='image/png')



# Endpoint to get image metadata
@webapp_router.get("/images/{image_id}/metadata")#, response_model=List[CategoryResponse]
def get_image_metadata(image_id: str, db: Session = Depends(get_db)):
    # Fetch the image by its ID (name field in this case)
    db_image = db.query(Image).filter_by(name=image_id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found.")

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
def get_image_ctf_data_route(image_name_or_oid: str, db: Session = Depends(get_db)):
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

    except NoResultFound:
        return HTTPException(status_code=404, detail="Image not found")

    db_ctf = db.query(ImageMetaData).filter(
        ImageMetaData.image_id == db_image.oid,
        ImageMetaData.data_json != None
    ).first()
    # if not db_ctf:
    #     raise HTTPException(status_code=404, detail="CTF data not found")
    #     # data_json is like : [{"key": "volts", "value": "300000.0"}, {"key": "cs", "value": "2.7"}, {"key": "apix", "value": "0.395"}, {"key": "defocus1", "value": "1.7631689452999998e-06"}, {"key": "defocus2", "value": "1.5946771484000002e-06"}, {"key": "angle_astigmatism", "value": "-1.1467587588191854"}, {"key": "amplitude_contrast", "value": "0.07"}, {"key": "extra_phase_shift", "value": "0.0"}, {"key": "confidence_30_10", "value": "-0.2375991372968843"}, {"key": "confidence_5_peak", "value": "-0.07497673401657018"}, {"key": "overfocus_conf_30_10", "value": "-0.26712254410180497"}, {"key": "overfocus_conf_5_peak", "value": "-0.10697129942661074"}, {"key": "resolution_80_percent", "value": "18.057936148038742"}, {"key": "resolution_50_percent", "value": "16.380544285663692"}, {"key": "confidence", "value": "-0.07497673401657018"}]
    #     # get re
    # data_json = db_ctf.data_json
    try:
        ctf_entry = next(item for item in db_ctf.data_json if item['key'] == 'CTF')
        ctf_value = ctf_entry['value']
        
        # If value is a string, it should be a stringified JSON, so we need to parse it
        if isinstance(ctf_value, str):
            ctf_data = json.loads(ctf_value)
        else:
            ctf_data = ctf_value  # If it's already a dictionary, use it directly
    except (KeyError, StopIteration, json.JSONDecodeError):
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
def get_ctf_image_route(name: str, image_type: str):
    try:
        session_name = name.split('_', 1)[0]  # Use split instead of find
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
def get_ctf_image_route(name: str, image_type: str):
    try:
        session_name = name.split('_', 1)[0]  # Use split instead of find
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
def get_image_data_route(name: str, db: Session = Depends(get_db)):
    db_image = ImageRepository.fetch_by_name(db, name)
    if db_image is None:
        raise HTTPException(status_code=404, detail="image not found with the given name")

    result = {
        "filename": db_image.name,
        "defocus": round(float(db_image.defocus) * 1.e6, 2),
        "PixelSize": round(float(db_image.pixel_size) * db_image.binning_x * 1.e10, 3),
        "mag": db_image.magnification,
        "dose": round(db_image.dose, 2) if db_image.dose is not None else "none",
    }
    return {'result': result}




@webapp_router.get('/parent_child')
def get_correct_image_parent_child(name: str, db_session: Session = Depends(get_db)):
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
    return {'result': "Done!"}


@webapp_router.post("/particle-pickings", summary="creates particle picking metadata for a given image and returns it",
                    status_code=201)
async def create_particle_picking(meta_name: str = Query(...), image_name_or_oid: str = Query(...),
                                  db: Session = Depends(get_db)):
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
def get_image_particles(img_name: str, db: Session = Depends(get_db)):
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
async def get_image_particle_by_id(oid: UUID, db: Session = Depends(get_db)):
    ppji = db.query(ImageMetaData).filter(ImageMetaData.Oid == oid).all()
    if not ppji:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitem found for Image")
    return ppji[0].data


@webapp_router.put("/particle-pickings", summary="Update particle picking data")
async def update_particle_picking(body_req: ParticlePickingDto, db_session: Session = Depends(get_db)):
    try:
        image_meta_data = db_session.query(ImageMetaData).filter(ImageMetaData.oid == body_req.oid).first()
        if not image_meta_data:
            raise HTTPException(status_code=404, detail="Particle picking  not found")
        if body_req.data:
            image_meta_data.data_json = json.loads(body_req.data)

        # db_session.merge(body_req)
        db_session.commit()
        db_session.refresh(image_meta_data)
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating Particle picking : {str(e)}")
    return image_meta_data


@webapp_router.get("/image_thumbnail")
async def get_image_thumbnail(name: str):
    underscore_index = name.find('_')
    session_name = name[:underscore_index]
    file_path = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name}/{IMAGE_SUB_URL}{name}.png"
    # Check if the file exists
    if not os.path.exists(file_path):
        # error_message = {"error": "Image not found"}
        # return JSONResponse(error_message, status_code=404)
        return get_image_not_found()

    return FileResponse(file_path, media_type='image/png')


@webapp_router.get("/atlases", response_model=List[AtlasDto])
async def get_session_atlases(session_name: str, db_session: Session = Depends(get_db)):
    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if msession is None:
        return {"error": "Session not found"}
    try:
        return db_session.query(Atlas).filter(Atlas.session_id == msession.oid).all()
    # session_id_binary = msession.Oid.bytes
    except AttributeError:
        return {"error": "Invalid session ID"}


@webapp_router.get("/atlas-image")
async def get_atlas_image(name: str):
    underscore_index = name.find('_')
    session_name = name[:underscore_index]
    file_path = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name}/{ATLAS_SUB_URL}/{name}.png"
    # Check if the file exists
    if not os.path.exists(file_path):
        # error_message = {"error": "Image not found"}
        # return JSONResponse(error_message, status_code=404)
        return get_image_not_found()

    return FileResponse(file_path, media_type='image/png')


@webapp_router.get("/image_thumbnail_url")
async def get_image_thumbnail_url(name: str):
    return f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{IMAGE_SUB_URL}{name}.png"

@webapp_router.get('/sessions', response_model=List[SessionDto])
def get_all_sessions(name: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Get all the sessions in database
    """
    if name:
        sessions = []
        db_msession = SessionRepository.fetch_by_name(db, name)
        print(db_msession)
        sessions.append(db_msession)
        return sessions
    else:
        return SessionRepository.fetch_all(db)


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
def create_leginon_atlas(session_name: str, db_session: Session = Depends(get_db)):


    # session_id = "13892"
    db_config = {
        "host": "127.0.0.1",
        "port": 3310,
        "user": "usr_object",
        "password": "ThPHMn3m39Ds",
        "db": "dbemdata",
        "charset": "utf8",
    }  # Create a connection to the MySQL database

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
    return {"images": images}



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
def create_magellon_atlas(session_name: str, db_session: Session = Depends(get_db)):
    """
    Create atlas images for a Magellon session using the Image table.
    """
    try:
        # Get the session ID from Msession table
        msession = db_session.query(Msession).filter(Msession.name == session_name).first()
        if not msession:
            raise HTTPException(status_code=404, detail="Session not found")
        if msession is None:
            return {"error": "Session not found"}
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

        return {"images": images}

    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail=str(e))




@webapp_router.get('/do_ctf')
async def get_do_image_ctf_route(full_image_path: str):
    # full_image_path="/gpfs/research/stagg/leginondata/23oct13x/rawdata/23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex.mrc"
    # session_name = "23oct13x"
    # file_name = "23oct13x_23oct13a_a_00034gr_00008sq_v02_00017hl_00003ex"

    # Extract file name without extension
    return await dispatch_ctf_task(uuid.uuid4(), full_image_path)


@webapp_router.get("/scan_directory")
async def get_directory_structure_route(path: str):
    return scan_directory(path)


# parse_xml_file(file: UploadFile = File(...)):
# contents = await file.read()
# results = parse_xml(contents)
# return json.dumps(results, indent=2)
@webapp_router.post("/parse-epu-xml/")
# async def parse_epu_xml_files(files: List[UploadFile] = File(...)):
async def parse_epu_xml_files(file: UploadFile = File(...)):
    epu_importer = EPUImporter()
    xml_contents = await file.read()
    # epu_importer.import_data(xml_contents)
    # epu_importer.process_imported_data()
    results = epu_importer.parse_epu_xml(xml_contents)
    return  results

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

@webapp_router.get("/directory-tree", response_model=List[DirectoryNode])
def directory_tree(root_path: str):
    root_path=r"C:\temp\test"
    return get_directory_structure(root_path)



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
async def get_images(file_path: str, start_idx: int = 0, count: int = 10) -> ImageResponse:
    """Get a subset of images from the MRC file."""
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
async def browse_directory(path: str = "/gpfs"):
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

        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@webapp_router.get("/test-motioncor")
async def test_motioncor(
        session_name: str = "24mar28a",
        file_name: str = "20241203_54449_integrated_movie"
):
    """
    API endpoint to test motioncor task creation and dispatch

    Args:
        session_name (str): Optional session name, defaults to "24mar28a"
        file_name (str): Optional file name, defaults to "20241203_54449_integrated_movie"

    Returns:
        dict: Status message indicating task creation result

    Raises:
        HTTPException: If task creation or queue push fails
    """
    try:
        motioncor_task = create_task(session_name, file_name)
        if not motioncor_task:
            raise HTTPException(
                status_code=500,
                detail="Failed to create motioncor task"
            )

        queue_result = push_task_to_task_queue(motioncor_task)

        if not queue_result:
            raise HTTPException(
                status_code=500,
                detail="Failed to push task to queue"
            )

        return {
            "status": "success",
            "message": "Motioncor task created and queued successfully",
            "task_id": str(motioncor_task.pid),
            "session_name": session_name
        }

    except Exception as e:
        logger.error(f"Error in test_motioncor endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


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