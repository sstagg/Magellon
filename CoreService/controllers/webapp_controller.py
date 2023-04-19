from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from config import FFT_DIR, THUMBNAILS_DIR, IMAGES_DIR, IMAGE_ROOT_URL, IMAGE_SUB_URL
from database import get_db
from models.sqlalchemy_models import Particlepickingjobitem, Image
from repositories.image_repository import ImageRepository
from services.file_service import FileService
from services.image_file_service import get_images, get_image_by_stack, get_image_data

webapp_router = APIRouter()
file_service = FileService()


@webapp_router.get('/images')
def get_images_route():
    return get_images()


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


# @webapp_router.get('/particles')
# def get_image_particles(name: str, db: Session = Depends(get_db)):
#     db_image = ImageRepository.fetch_by_name(db, name)
#     if db_image is None:
#         raise HTTPException(status_code=404, detail="image not found with the given name")
#
#     # Get all Particlepickingjobitems associated with the image
#     db_ppis = db.query(Particlepickingjobitem).filter(Particlepickingjobitem.image == db_image.Oid).all()
#     if db_ppis is None:
#         raise HTTPException(status_code=404, detail="Particle Picking not found for given image name")
#     return db_ppis


@webapp_router.get('/particles')
def get_image_particles(image_name: str, db: Session = Depends(get_db)):
    particlepickingjobitems = db.query(Particlepickingjobitem).join(Image).filter(Image.name == image_name).all()
    if not particlepickingjobitems:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitems found for Image")
    return particlepickingjobitems


@webapp_router.get('/particles/{oid}', summary="gets an image particles json by its unique id")
def get_image_particle_by_id(oid: UUID, db: Session = Depends(get_db)):
    ppji = db.query(Particlepickingjobitem).filter(Particlepickingjobitem.Oid == oid).all()
    if not ppji:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitem found for Image")
    return ppji[0].data


@webapp_router.put("/particles/{oid}", summary="gets particles oid and data and updates it")
def update_particle_picking_jobitem(oid: UUID,
                                    req_body: str,
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
