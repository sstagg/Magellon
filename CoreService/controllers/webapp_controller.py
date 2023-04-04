from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from repositories.image_repository import ImageRepository
from services.image_service import get_images, get_image_by_stack, get_fft_image, get_image_data

webapp_router = APIRouter()


@webapp_router.get('/images')
def get_images_route():
    return get_images()


@webapp_router.get('/images_by_stack')
def get_images_by_stack_route(ext: str):
    return get_image_by_stack(ext)


@webapp_router.get('/fft_image')
def get_fft_image_route(name: str):
    return get_fft_image(name)


@webapp_router.get('/image_data')
def get_image_data_route(name: str, db: Session = Depends(get_db)):
    db_image = ImageRepository.fetch_by_name(db, name)
    if db_image is None:
        raise HTTPException(status_code=404, detail="image not found with the given name")
    return get_image_data(db_image)


@webapp_router.get("/image_thumbnail")
async def get_image_thumbnail(name: str):
    # folder = Path(BASE_PATH) / "images"
    return get_image_thumbnail(name)

# @image_viewer_router.get("/download_file")
# async def download_file(file_path: str):
#     return FileResponse(path=file_path, filename=file_path.split("/")[-1])
#
#
# @image_viewer_router.get("/download_png/{name}")
# async def download_png(name: str):
#     folder = Path(BASE_PATH) / "images"
#     file_path = folder / f"{name}.png"
#     if not file_path.is_file():
#         return "File not found", 404
#     file_stream = file_path.open("rb")
#     return StreamingResponse(file_stream, media_type="image/png")
