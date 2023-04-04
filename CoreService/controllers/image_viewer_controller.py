from fastapi import APIRouter, Depends
from fastapi import Query
from fastapi.responses import FileResponse
from pathlib import Path

from starlette.responses import StreamingResponse

from config import BASE_PATH
from services.image_service import get_images

image_viewer_router = APIRouter()


@image_viewer_router.get('/get_images')
def get_images_route():
    return get_images()


#
#
# @image_viewer_router.get('/get_image_by_thumbnail')
# def get_image_by_thumbnail_route(query: ImageByThumbnailQuery):
#     return get_image_thumbnail()
#
#
# @image_viewer_router.get('/get_images_by_stack')
# def get_images_by_stack_route(query: StackImagesQuery):
#     return get_image_by_stack()
#
#
# @image_viewer_router.get('/get_fft_image')
# def get_fft_image_route(query: FFTImageQuery):
#     return get_fft_image()
#
#
# @image_viewer_router.get('/get_image_data')
# def get_image_data_route(query: ImageMetadataQuery):
#     return get_image_data()
@image_viewer_router.get("/image_thumbnail")
async def get_image_thumbnail(name: str = Query(...)):
    folder = Path(BASE_PATH) / "images"
    return FileResponse(folder / f"{name}.png")


@image_viewer_router.get("/download_file")
async def download_file(file_path: str):
    return FileResponse(path=file_path, filename=file_path.split("/")[-1])


@image_viewer_router.get("/download_png/{name}")
async def download_png(name: str):
    folder = Path(BASE_PATH) / "images"
    file_path = folder / f"{name}.png"
    if not file_path.is_file():
        return "File not found", 404
    file_stream = file_path.open("rb")
    return StreamingResponse(file_stream, media_type="image/png")
