
import json
import os
import uuid
from typing import List, Optional
from uuid import UUID

import airflow_client.client
from airflow_client.client import ApiClient
from airflow_client.client.api import dag_run_api
from airflow_client.client.model.dag_run import DAGRun

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload
from starlette.responses import FileResponse, JSONResponse

from config import FFT_SUB_URL, IMAGE_SUB_URL, IMAGE_ROOT_DIR, THUMBNAILS_SUB_URL, app_settings, THUMBNAILS_SUFFIX, \
    FFT_SUFFIX

from database import get_db
from lib.image_not_found import get_image_not_found
from models.pydantic_models import ParticlepickingjobitemDto, MicrographSetDto, SessionDto
from models.sqlalchemy_models import Particlepickingjobitem, Image, Particlepickingjob, Msession
from repositories.image_repository import ImageRepository
from repositories.session_repository import SessionRepository
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


@webapp_router.get('/images')
def get_images_route(session_name: str, level: int, db_session: Session = Depends(get_db)):
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
        SELECT
          child.Oid,
          child.name,
          child.level,
          child.parent_id,
          child.parent_name
        FROM (
          SELECT
            image.Oid,
            image.name,
            image.parent_id,
            parent.name AS parent_name,
            image.level,
            ROW_NUMBER() OVER (PARTITION BY image.parent_id ORDER BY image.oid) AS row_num,
            image.session_id
          FROM image
          INNER JOIN image parent ON image.parent_id = parent.Oid
          WHERE image.level = :level
            AND image.session_id = :session_id
        ) child
        WHERE child.row_num <= 3
        GROUP BY child.parent_name, child.Oid, child.name, child.parent_id, child.level, child.session_id
    """)
    return execute_images_query(db_session, query, session_name, {"level": level, "session_id": session_id_binary})


@webapp_router.get('/images_by_stack')
def get_images_by_stack_route(ext: str, db_session: Session = Depends(get_db)):
    try:
        session_name = "22apr01a"
        query = text("""
            SELECT
              image.Oid,
              image.name,
              image.level,
              image.parent_id,
              parent.name AS parent_name
            FROM image parent
              INNER JOIN image
                ON image.parent_id = parent.Oid
            WHERE parent.name = :image_name
                """)
        return execute_images_query(db_session, query, session_name, {"image_name": ext})

    except Exception as e:
        return {"error": str(e)}


def execute_images_query(db_session: Session, query, session_name, params=None):
    try:
        # result = db_session.execute(query) if params is None else db_session.execute(query, params)
        result = db_session.execute(query, params)
        rows = result.fetchall()
        return {"result": (process_image_rows(rows, session_name))}
    except Exception as e:
        raise Exception(f"Database query execution error: {str(e)}")


def process_image_rows(rows, session_name):
    images_by_parent = {}
    for row in rows:
        oid, name, level, parent_id, parent_name = row[:5]
        image = MicrographSetDto(
            oid=oid,
            name=name,
            level=level,
            parent_id=parent_id,
            parent_name=parent_name
        )
        file_path = os.path.join(f"{IMAGE_ROOT_DIR}/{session_name}/{THUMBNAILS_SUB_URL}",
                                 image.name + THUMBNAILS_SUFFIX)
        print(file_path)
        if os.path.isfile(file_path):
            image.encoded_image = get_response_image(file_path)

        if image.parent_name not in images_by_parent:
            images_by_parent[image.parent_name] = []

        images_by_parent[image.parent_name].append(image)

    result_list = [
        {"ext": parent_name, "images": images}
        for parent_name, images in images_by_parent.items()
    ]

    return result_list


@webapp_router.get('/fft_image')
def get_fft_image_route(name: str):
    file_path = f"{IMAGE_ROOT_DIR}/{FFT_SUB_URL}{name}{FFT_SUFFIX}"
    return FileResponse(file_path, media_type='image/png')


@webapp_router.get('/image_data')
def get_image_data_route(name: str, db: Session = Depends(get_db)):
    db_image = ImageRepository.fetch_by_name(db, name)
    if db_image is None:
        raise HTTPException(status_code=404, detail="image not found with the given name")
    result = {
        "filename": db_image.name,
        "defocus": round(float(db_image.defocus) * 1.e6, 2),
        "PixelSize": round(float(db_image.pixel_size) * db_image.binning_x, 3),
        "mag": db_image.magnification,
        "dose": round(db_image.dose, 2) if db_image.dose is not None else "none",
    }
    return {'result': result}


@webapp_router.get('/particles')
def get_image_particles(img_name: str, db: Session = Depends(get_db)):
    # result = \
    #     db.query(Particlepickingjobitem,  Particlepickingjob.name). \
    #     join(Image, Particlepickingjobitem.image_id == Image.Oid). \
    #     join(Particlepickingjob, Particlepickingjobitem.job == Particlepickingjob.Oid).filter(Image.name == img_name).\
    #     options( joinedload(Particlepickingjobitem.particlepickingjob)). \
    #     all()

    result = db.query(Particlepickingjobitem, Particlepickingjob.name). \
        join(Image, Particlepickingjobitem.image_id == Image.Oid). \
        join(Particlepickingjob, Particlepickingjobitem.job.has(Particlepickingjob.Oid)). \
        filter(Image.name == img_name). \
        options(joinedload(Particlepickingjobitem.job)). \
        all()

    if not result:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitems found for Image")

    response = []

    for row in result:
        particlepickingjobitem, job_name = row
        response.append(ParticlepickingjobitemDto(
            Oid=particlepickingjobitem.Oid,
            job=particlepickingjobitem.job,
            # job_name=particlepickingjobitem.particlepickingjob.name,
            job_name=job_name,
            image=particlepickingjobitem.image,
            data=json.dumps(particlepickingjobitem.settings),
            status=particlepickingjobitem.status,
            type=particlepickingjobitem.type
        ))
    return response


@webapp_router.get('/particles/{oid}', summary="gets an image particles json by its unique id")
def get_image_particle_by_id(oid: UUID, db: Session = Depends(get_db)):
    ppji = db.query(Particlepickingjobitem).filter(Particlepickingjobitem.Oid == oid).all()
    if not ppji:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitem found for Image")
    return ppji[0].data


@webapp_router.put("/particles/{oid}", summary="gets particles oid and data and updates it")
def update_particle_picking_jobitem(oid: UUID,
                                    req_body: dict,
                                    db: Session = Depends(get_db)):
    try:
        db_item = db.query(Particlepickingjobitem).filter(Particlepickingjobitem.Oid == oid).first()
        if not db_item:
            raise HTTPException(status_code=404, detail="Particle picking job item not found")
        db_item.data = req_body
        db.commit()
        db.refresh(db_item)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating Particle picking job item: {str(e)}")
    return db_item


@webapp_router.get("/image_by_thumbnail")
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
        db_camera = SessionRepository.fetch_by_name(db, name)
        print(db_camera)
        sessions.append(db_camera)
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
