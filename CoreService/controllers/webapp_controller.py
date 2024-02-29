import re
from datetime import datetime
import json
import os
import uuid
from typing import List, Optional
from uuid import UUID

import airflow_client.client
import pymysql
from airflow_client.client import ApiClient
from airflow_client.client.api import dag_run_api
from airflow_client.client.model.dag_run import DAGRun

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, joinedload
from starlette.responses import FileResponse, JSONResponse

from config import FFT_SUB_URL, IMAGE_SUB_URL, IMAGE_ROOT_DIR, THUMBNAILS_SUB_URL, app_settings, THUMBNAILS_SUFFIX, \
    FFT_SUFFIX, ATLAS_SUB_URL

from database import get_db
from lib.image_not_found import get_image_not_found
from models.pydantic_models import ParticlepickingjobitemDto, MicrographSetDto, SessionDto, ImageDto, AtlasDto, \
    ParticlePickingDto
from models.sqlalchemy_models import Particlepickingjobitem, Image, Particlepickingjob, Msession, Atlas, ImageMetadata
from repositories.image_repository import ImageRepository
from repositories.session_repository import SessionRepository
from services.atlas import create_atlas_images
from services.file_service import FileService
from services.helper import get_response_image

# from services.image_file_service import get_images, get_image_by_stack, get_image_data

webapp_router = APIRouter()
file_service = FileService("transfer.log")


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
        session_id_binary = msession.Oid.bytes
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
        session_id_binary = msession.Oid.bytes
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
          i.Oid,
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
            WHERE c.parent_id = i.Oid
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
                oid=row.Oid,
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
            session_id_binary = msession.Oid.bytes
        except AttributeError:
            raise HTTPException(status_code=500, detail="Invalid session ID")

        # Fetch the single image based on the image name
        query = text("""
            SELECT
              i.Oid,
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
                oid=row.Oid,
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


# @webapp_router.get('/images')
# def get_images_route(session_name: str, mag: int, db_session: Session = Depends(get_db)):
#     # session_name = "22apr01a"
#     # level = 4
#
#     # Get the Msession based on the session name
#     msession = db_session.query(Msession).filter(Msession.name == session_name).first()
#     if msession is None:
#         return {"error": "Session not found"}
#
#     try:
#         session_id_binary = msession.Oid.bytes
#     except AttributeError:
#         return {"error": "Invalid session ID"}
#
#     query = text("""
#         SELECT
#           child.Oid,
#           child.name,
#           child.level,
#           child.parent_id,
#           child.parent_name
#         FROM (
#           SELECT
#             image.Oid,
#             image.name,
#             image.parent_id,
#             parent.name AS parent_name,
#             image.level,
#             image.magnification,
#             ROW_NUMBER() OVER (PARTITION BY image.parent_id ORDER BY image.oid) AS row_num,
#             image.session_id
#           FROM image
#           INNER JOIN image parent ON image.parent_id = parent.Oid
#           WHERE image.magnification = :mag
#             AND image.session_id = :session_id
#         ) child
#         WHERE child.row_num <= 3
#         GROUP BY child.parent_name, child.Oid, child.name, child.parent_id, child.level, child.session_id
#     """)
#     return execute_images_query(db_session, query, session_name, {"mag": mag, "session_id": session_id_binary})
#
#
# @webapp_router.get('/images_by_stack')
# def get_images_by_stack_route(ext: str, db_session: Session = Depends(get_db)):
#     try:
#         parts = ext.split('_')
#         if len(parts) >= 1:
#             session_name = parts[0]
#         else:
#             return {"error": "Session is not included in the file name"}
#
#         # session_name = parts[0] if parts else None
#
#         query = text("""
#             SELECT
#               image.Oid,
#               image.name,
#               image.level,
#               image.parent_id,
#               parent.name AS parent_name
#             FROM image parent
#               INNER JOIN image
#                 ON image.parent_id = parent.Oid
#             WHERE parent.name = :image_name
#                 """)
#         return execute_images_query(db_session, query, session_name, {"image_name": ext})
#
#     except Exception as e:
#         return {"error": str(e)}
#
#
# def execute_images_query(db_session: Session, query, session_name, params=None):
#     try:
#         # result = db_session.execute(query) if params is None else db_session.execute(query, params)
#         result = db_session.execute(query, params)
#         rows = result.fetchall()
#         return {"result": (process_image_rows(rows, session_name))}
#     except Exception as e:
#         raise Exception(f"Database query execution error: {str(e)}")
#
#
# def process_image_rows(rows, session_name):
#     images_by_parent = {}
#     for row in rows:
#         oid, name, level, parent_id, parent_name = row[:5]
#         image = MicrographSetDto(
#             oid=oid,
#             name=name,
#             level=level,
#             parent_id=parent_id,
#             parent_name=parent_name
#         )
#         file_path = os.path.join(f"{IMAGE_ROOT_DIR}/{session_name}/{THUMBNAILS_SUB_URL}",
#                                  image.name + THUMBNAILS_SUFFIX)
#         print(file_path)
#         if os.path.isfile(file_path):
#             image.encoded_image = get_response_image(file_path)
#
#         if parent_id not in images_by_parent:
#             parent_path = os.path.join(f"{IMAGE_ROOT_DIR}/{session_name}/{THUMBNAILS_SUB_URL}",
#                                        parent_name + THUMBNAILS_SUFFIX)
#             parent_image = get_response_image(parent_path) if os.path.isfile(parent_path) else None
#             images_by_parent[parent_id] = {
#                 "parent_id": uuid.UUID(bytes=parent_id),
#                 "encoded_image": parent_image,
#                 "parent_name": parent_name,
#                 "images": []
#             }
#
#         images_by_parent[parent_id]["images"].append(image)
#
#     result_list = list(images_by_parent.values())
#     return result_list
#

@webapp_router.get('/fft_image')
def get_fft_image_route(name: str):
    underscore_index = name.find('_')
    session_name = name[:underscore_index]
    file_path = f"{app_settings.directory_settings.IMAGE_ROOT_DIR}/{session_name}/{FFT_SUB_URL}{name}{FFT_SUFFIX}"
    return FileResponse(file_path, media_type='image/png')


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


def get_stripped_parent(input_string):
    # Define the regular expression pattern to match "_v01", "_v02", "-b", "-DW"
    pattern = r"(_[vV]\d{2})|(-[bB])|(-[dD][wW])"
    # Use re.sub() to remove the matched substrings
    return re.sub(pattern, '', input_string)


def get_parent_name(child_name):
    split_name = child_name.split('_')
    # if split_name[-1] == 'v01':
    if re.search(r'[vV]([0-9][0-9])', split_name[-1]):
        parent_name = '_'.join(split_name[:-2])
    else:
        parent_name = '_'.join(split_name[:-1])
    # Join the parts back together with underscores and return
    return parent_name


@webapp_router.get('/parent_child')
def get_correct_image_parent_child(name: str, db_session: Session = Depends(get_db)):
    db_image_list = ImageRepository.fetch_all_by_session_name(db_session, name)
    if not db_image_list:
        raise HTTPException(status_code=404, detail="images not found with the given name")
    image_dict = {}
    # for db_image in db_image_list:
    #     image_dict[db_image.name] = db_image.Oid
    image_dict = {db_image.name: db_image.Oid for db_image in db_image_list}

    for db_image in db_image_list:
        parent_name = get_parent_name(db_image.name)

        if parent_name in image_dict:
            db_image.parent_id = image_dict[parent_name]
    db_session.bulk_save_objects(db_image_list)
    db_session.commit()
    return {'result': "Done!"}


@webapp_router.post("/particle-pickings", summary="creates particle picking metadata for a given image and returns it", status_code=201)
async def create_particle_picking(meta_name: str = Query(...),image_name_or_oid: str = Query(...), db: Session = Depends(get_db)):
    try:
        try:
            # Attempt to convert image_name_or_oid to UUID
            image_uuid = UUID(image_name_or_oid)
            # If convertible to UUID, search by OID
            image = db.query(Image).filter_by(Oid=image_uuid).first()
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
        image_meta_data = db.query(ImageMetadata).filter_by(name=meta_name).one()
    except NoResultFound:
        # If it doesn't exist, create a new one
        image_meta_data = ImageMetadata(

            OID=uuid.uuid4(),
            name=meta_name,
            # description="manual job for particle picking",
            created_on=datetime.now(),
            image_id=image.Oid,
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
    result = db.query(ImageMetadata). \
        join(Image, ImageMetadata.image_id == Image.Oid). \
        filter(Image.name == img_name). \
        all()
    if not result:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitems found for Image")
    response = []
    for row in result:
        image_meta_data = row
        response.append(ParticlePickingDto(
            oid=image_meta_data.OID,
            name=image_meta_data.name,
            image_id=image_meta_data.image_id,
            data_json=json.dumps(image_meta_data.data_json),
            # status=particlepickingjobitem.status,
            # type=particlepickingjobitem.type
        ))
    return response


# FastAPI endpoint to create a ParticlePickingjobitem
# @webapp_router.post("/create_ppji/", summary="creates particle picking job item for a given image and returns it")
# async def create_particle_picking_jobitem(image_name_or_oid: str = Query(...), db: Session = Depends(get_db)):
#     try:
#         try:
#             # Attempt to convert image_name_or_oid to UUID
#             image_uuid = UUID(image_name_or_oid)
#             # If convertible to UUID, search by OID
#             image = db.query(Image).filter_by(Oid=image_uuid).first()
#         except ValueError:
#             # If not convertible to UUID, search by filename
#             image = db.query(Image).filter_by(name=image_name_or_oid).first()
#
#         if not image:
#             return HTTPException(status_code=404, detail="Image not found")
#
#     except NoResultFound:
#         # db.close()
#         return HTTPException(status_code=404, detail="Image not found")
#
#     try:
#         # Check if a "manual" Particlepickingjob already exists
#         manual_job = db.query(Particlepickingjob).filter_by(name="manual").one()
#     except NoResultFound:
#         # If it doesn't exist, create a new one
#         manual_job = Particlepickingjob(
#             Oid=uuid.uuid4(),
#             name="manual",
#             description="manual job for particle picking",
#             created_on=datetime.now(),
#             msession=image.msession if image.msession is not None else None,
#             # Add other necessary fields here
#         )
#         # if image.msession is not None:
#         #     # Include the image's session in the job and item
#         #     manual_job.msession = image.msession
#         db.add(manual_job)
#         db.commit()
#         db.refresh(manual_job)
#
#     # Create the ParticlePickingjobitem
#     try:
#         jobitem = Particlepickingjobitem(
#             Oid=uuid.uuid4(),
#             job_id=manual_job.Oid,
#             image_id=image.Oid,
#
#             # Add other necessary fields here
#         )
#
#         db.add(jobitem)
#         db.commit()
#         db.refresh(jobitem)
#
#         return jobitem
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=str(e))


# @webapp_router.get('/particles')
# def get_image_particles(img_name: str, db: Session = Depends(get_db)):
#     # result = \
#     #     db.query(Particlepickingjobitem,  Particlepickingjob.name). \
#     #     join(Image, Particlepickingjobitem.image_id == Image.Oid). \
#     #     join(Particlepickingjob, Particlepickingjobitem.job == Particlepickingjob.Oid).filter(Image.name == img_name).\
#     #     options( joinedload(Particlepickingjobitem.particlepickingjob)). \
#     #     all()
#
#     result = db.query(Particlepickingjobitem, Particlepickingjob.name). \
#         join(Image, Particlepickingjobitem.image_id == Image.Oid). \
#         join(Particlepickingjob, Particlepickingjobitem.job.has(Particlepickingjob.Oid)). \
#         filter(Image.name == img_name). \
#         options(joinedload(Particlepickingjobitem.job)). \
#         all()
#
#     if not result:
#         raise HTTPException(status_code=404, detail="No Particlepickingjobitems found for Image")
#
#     response = []
#
#     for row in result:
#         particlepickingjobitem, job_name = row
#         response.append(ParticlepickingjobitemDto(
#             Oid=particlepickingjobitem.Oid,
#             job=particlepickingjobitem.job,
#             # job_name=particlepickingjobitem.particlepickingjob.name,
#             job_name=job_name,
#             image=particlepickingjobitem.image,
#             data=json.dumps(particlepickingjobitem.settings),
#             status=particlepickingjobitem.status,
#             type=particlepickingjobitem.type
#         ))
#     return response


@webapp_router.get('/particles/{oid}', summary="gets an image particles json by its unique id")
async def get_image_particle_by_id(oid: UUID, db: Session = Depends(get_db)):
    ppji = db.query(ImageMetadata).filter(ImageMetadata.Oid == oid).all()
    if not ppji:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitem found for Image")
    return ppji[0].data


@webapp_router.put("/particle-pickings", summary="Update particle picking data")
async def update_particle_picking(body_req: ParticlePickingDto, db_session: Session = Depends(get_db)):
    try:
        image_meta_data = db_session.query(ImageMetadata).filter(ImageMetadata.OID == body_req.oid).first()
        if not image_meta_data:
            raise HTTPException(status_code=404, detail="Particle picking  not found")
        image_meta_data.data_json = image_meta_data.data_json
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
    file_path = f"{app_settings.directory_settings.IMAGE_ROOT_DIR}/{session_name}/{IMAGE_SUB_URL}{name}.png"
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
        return db_session.query(Atlas).filter(Atlas.session_id == msession.Oid).all()
    # session_id_binary = msession.Oid.bytes
    except AttributeError:
        return {"error": "Invalid session ID"}


@webapp_router.get("/atlas-image")
async def get_atlas_image(name: str):
    underscore_index = name.find('_')
    session_name = name[:underscore_index]
    file_path = f"{app_settings.directory_settings.IMAGE_ROOT_DIR}/{session_name}/{ATLAS_SUB_URL}/{name}.png"
    # Check if the file exists
    if not os.path.exists(file_path):
        # error_message = {"error": "Image not found"}
        # return JSONResponse(error_message, status_code=404)
        return get_image_not_found()

    return FileResponse(file_path, media_type='image/png')


@webapp_router.get("/image_thumbnail_url")
async def get_image_thumbnail_url(name: str):
    return f"{app_settings.directory_settings.IMAGE_ROOT_DIR}/{IMAGE_SUB_URL}{name}.png"


# @webapp_router.post("/transfer_files")
# async def transfer_files(source_path: str, destination_path: str, delete_original: bool = False,
#                          compress: bool = False):
#     try:
#         file_service.transfer_files(source_path, destination_path, delete_original)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
#     else:
#         return {"message": "Files transferred successfully."}


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


@webapp_router.post("/run_dag")
async def run_dag():
    try:
        # post 'http://128.186.103.43:8383/api/v1/dags/my_dag/dagRuns'
        configuration = airflow_client.client.Configuration(
            host="http://128.186.103.43:8383/api/v1",

            username='admin',
            password='admin'
        )
        configuration.verify_ssl = False
        DAG_ID = "my_dag"
        # Enter a context with an instance of the API client
        api_client = ApiClient(configuration)

        errors = False

        # print('[blue]Getting DAG list')
        # dag_api_instance = dag_api.DAGApi(api_client)
        #
        # try:
        #     api_response = dag_api_instance.get_dags()
        #     print(api_response)
        # except airflow_client.client.OpenApiException as e:
        #     print("[red]Exception when calling DagAPI->get_dags: %s\n" % e)
        #     errors = True
        # else:
        #     print('[green]Getting DAG list successful')

        print('[blue]Triggering a DAG run')
        dag_run_api_instance = dag_run_api.DAGRunApi(api_client)
        try:
            # Create a DAGRun object (no dag_id should be specified because it is read-only property of DAGRun)
            # dag_run id is generated randomly to allow multiple executions of the script
            dag_run = DAGRun(
                dag_run_id='some_test_run_' + uuid.uuid4().hex,
            )
            api_response = dag_run_api_instance.post_dag_run(DAG_ID, dag_run)
            print(api_response)
        except airflow_client.client.exceptions.OpenApiException as e:
            print("[red]Exception when calling DAGRunAPI->post_dag_run: %s\n" % e)
            errors = True
        else:
            print('[green]Posting DAG Run successful')


    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    else:
        return {"message": "Files transferred successfully."}


@webapp_router.get("/create_atlas")
async def create_atlas(session_name: str, db_session: Session = Depends(get_db)):
    # Define the database connection parameters
    # session_id = request_data.session_id
    # if session_id.strip() == "":
    #     raise HTTPException(status_code=400, detail="Session ID is empty")
    # session_id = "13984"
    # session_id = "13892"

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

    query1 = "SELECT label FROM ImageTargetListData WHERE `REF|SessionData|session` = %s AND mosaic = %s"

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
    # result_json = json.dumps(label_objects, indent=2)
    # return result_json

    # Now, 'label_objects' is a dictionary where labels are keys, and values are lists of associated dictionaries
    # for label, objects in label_objects.items():
    #     print(f"{label}: {objects}")
    images = await create_atlas_images(session_name, label_objects)

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

# @image_viewer_router.get("/download_file")
# async def download_file(file_path: str):
#     return FileResponse(path=file_path, filename=file_path.split("/")[-1])

# @image_viewer_router.get("/download_png/{name}")
# async def download_png(name: str):
#     folder = Path(BASE_PATH) / "images"
#     file_path = folder / f"{name}.png"
#     if not file_path.is_file():
#         return "File not found", 404
#     file_stream = file_path.open("rb")
#     return StreamingResponse(file_stream, media_type="image/png")
