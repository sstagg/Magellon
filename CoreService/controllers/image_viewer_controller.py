# from fastapi import APIRouter, Depends
#
#
# image_viewer_router = APIRouter()
#
#
#
# @image_viewer_router.get('/get_images')
# def get_images_route():
#     return get_images()
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