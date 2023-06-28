import json
import uuid
from typing import List
from uuid import UUID

import airflow_client.client
from airflow_client.client import ApiClient
from airflow_client.client.api import config_api, dag_api, dag_run_api
from airflow_client.client.model.dag_run import DAGRun

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload
from starlette.responses import FileResponse

from config import FFT_DIR, IMAGES_DIR, IMAGE_ROOT_URL, IMAGE_SUB_URL
from database import get_db
from models.pydantic_models import ParticlepickingjobitemDto, MicrographSetDto
from models.sqlalchemy_models import Particlepickingjobitem, Image, Particlepickingjob, Msession
from repositories.image_repository import ImageRepository
from services.file_service import FileService
from services.image_file_service import get_images, get_image_by_stack, get_image_data

webapp_router = APIRouter()
file_service = FileService("transfer.log")


@webapp_router.get('/images_old')
def get_images_old_route():
    return get_images()


@webapp_router.get('/images_by_stack_old')
def get_images_by_stack_old_route(ext: str):
    return get_image_by_stack(ext)


@webapp_router.get('/images')
# def get_images_route(session_name: str, level: int, db_session: Session = Depends(get_db)):
def get_images_route( db_session: Session = Depends(get_db)):
    session_name = "22apr01a"
    level=4
    # Get the Msession based on the session name
    msession = db_session.query(Msession).filter(Msession.name == session_name).first()
    if msession is None:
        return {"error": "Session not found"}

    result = db_session.execute(text("""
            SELECT DISTINCT
                partitioned_images.parent_name,
                partitioned_images.Oid,
                partitioned_images.name,
                partitioned_images.parent_id,
                partitioned_images.level
            FROM (
                SELECT
                    child.Oid,
                    child.name,
                    child.parent_id,
                    parent.name AS parent_name,
                    child.level,
                    ROW_NUMBER() OVER (PARTITION BY child.parent_id ORDER BY child.oid) AS row_num
                FROM image child
                LEFT OUTER JOIN image parent ON child.parent_id = parent.Oid
                WHERE child.level = 4
            ) partitioned_images
            WHERE partitioned_images.row_num <= 3
        """))
    rows = result.fetchall()
    # Retrieve all images in the specified level
    # images = db_session.query(Image).filter(Image.session_id == msession.Oid, Image.level == level).all()
    # Convert the query result to a dictionary with parent_name as key and associated images as value
    images = {}
    for row in rows:
        # image = MicrographSetDto(oid=row["oid"], name=row["name"], parent_id=row["parent_id"], level=row["level"])
        image = MicrographSetDto(parent_name=row[0],id=row[1], name=row[2], parent_id=row[3], level=row[4])
        parent_name = row[0]
        # parent_name = row["parent_name"]
        if parent_name not in images:
            images[parent_name] = []
        images[parent_name].append(image)

    return images
    # Prepare the response
    # image_data = []
    # for image in images:
    #     image_data.append({
    #         "oid": str(image.Oid),
    #         "name": image.name,
    #         "path": image.path,
    #         # Include other desired image attributes
    #     })
    #
    # return {"images": image_data}

    # return get_images()


@webapp_router.get('/images_by_stack')
def get_images_by_stack_route(ext: str):
    return get_image_by_stack(ext)


@webapp_router.get('/fft_image')
def get_fft_image_route(name: str):
    file_path = f"{FFT_DIR}{name}.png"
    return FileResponse(file_path, media_type='image/png')


@webapp_router.get('/image_data')
def get_image_data_route(name: str, db: Session = Depends(get_db)):
    db_image = ImageRepository.fetch_by_name(db, name)
    if db_image is None:
        raise HTTPException(status_code=404, detail="image not found with the given name")
    return get_image_data(db_image)


@webapp_router.get('/particles')
def get_image_particles(img_name: str, db: Session = Depends(get_db)):
    # result = \
    #     db.query(Particlepickingjobitem,  Particlepickingjob.name). \
    #     join(Image, Particlepickingjobitem.image == Image.Oid). \
    #     join(Particlepickingjob, Particlepickingjobitem.job == Particlepickingjob.Oid).filter(Image.name == img_name).\
    #     options( joinedload(Particlepickingjobitem.particlepickingjob)). \
    #     all()
    result = db.query(Particlepickingjobitem, Particlepickingjob.name). \
        join(Particlepickingjob, Particlepickingjobitem.job == Particlepickingjob.Oid).filter(
        Particlepickingjobitem.image1.has(name=img_name)). \
        options(joinedload(Particlepickingjobitem.particlepickingjob)). \
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
    file_path = f"{IMAGES_DIR}{name}.png"
    return FileResponse(file_path, media_type='image/png')


@webapp_router.get("/image_thumbnail_url")
async def get_image_thumbnail_url(name: str):
    return f"{IMAGE_ROOT_URL}{IMAGE_SUB_URL}{name}.png"


@webapp_router.post("/transfer_files")
async def transfer_files(source_path: str, destination_path: str, delete_original: bool = False,
                         compress: bool = False):
    try:
        file_service.transfer_files(source_path, destination_path, delete_original)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    else:
        return {"message": "Files transferred successfully."}


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
