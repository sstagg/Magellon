from starlette.responses import FileResponse, StreamingResponse, JSONResponse

from config import BASE_PATH
from pathlib import Path


import glob
import os

from pydantic import BaseModel

from config import BASE_PATH

from services.helper import get_response_image, format_data_by_ext


# class ImageMetadataQuery(BaseModel):
#     name: str
#
#
# class FFTImageQuery(BaseModel):
#     name: str
#
#
# class StackImagesQuery(BaseModel):
#     ext: str
#
#
# class ImageByThumbnailQuery(BaseModel):
#     name: str
#
#
def get_images():
    encoded_images = []
    data = []
    root_dir = os.path.join(BASE_PATH, "thumbnails")
    # root_dir = r"%s/thumbnails/" % BASE_PATH
    filename_list = os.listdir(root_dir)
    parent_file_ext = set()
    for filename in filename_list:
        if len(filename.split("_")) > 6:
            parent_file_ext.add(filename.split("_")[5])
        else:
            parent_file_ext.add('misc')
    stack_3_images_list = set()
    for ext in parent_file_ext:
        count = 0
        for filename in filename_list:
            if (ext in filename) and len(filename.split("_")) >= 6 and (
                    filename.endswith(ext + '_TIMG.png')) and count == 0:
                stack_3_images_list.add(filename)
                count += 1

        for filename in filename_list:
            if (ext in filename) and not filename.endswith(ext + '_TIMG.png') and count < 3:
                # print("else 3 filenames - ", filename)
                stack_3_images_list.add(filename)
                count += 1
    for filename in glob.iglob(root_dir + '*.png', recursive=True):
        if filename.rsplit("/", 1)[1] not in stack_3_images_list:
            continue
        item = {}
        short_name = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]  # get image name
        item['name'] = short_name
        item['encoded_image'] = get_response_image(filename)
        item['ext'] = short_name.split("_")[5] if len(short_name.split("_")) > 5 else "misc"
        data.append(item)
    res = format_data_by_ext(data)
    return JSONResponse(content={'result': res}, headers={'Access-Control-Allow-Origin': '*'})

#
# def get_image_by_stack():
#     args = request.args
#     ext = args.get('ext')
#     encoded_images = []
#     data = []
#     ''' path contains list of mrc thumbnails '''
#     root_dir = r"%s/thumbnails/" % BASE_PATH
#     for filename in glob.iglob(root_dir + '*.png', recursive=True):
#         item = {}
#         shortName = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]  # get image name
#         item['name'] = shortName
#         item['ext'] = shortName.split("_")[5] if len(shortName.split("_")) > 5 else "misc"
#         if ext == item['ext']:
#             item['encoded_image'] = get_response_image(filename)
#             data.append(item)
#     res = format_data_by_ext(data)
#     response = jsonify({'result': res})
#     response.headers.add('Access-Control-Allow-Origin', '*')
#     return response
#
#
# def get_image_data():
#     args = request.args
#     name = args.get('name')
#     data = mgDatabase.getImageData(name)
#     ''' Get pixel size in Angstroms '''
#     pixelsize = mgDatabase.getPixelSize(data)
#     ''' Get dose in electrons per Angstrom '''
#     dose = mgDatabase.getDoseFromImageData(data)
#     item = {}
#     item['defocus'] = round(data['preset']['defocus'] * 1.e6, 2)
#     item['mag'] = data['preset']['magnification']
#     item['filename'] = data['filename']
#     item['pixelsize'] = round(pixelsize, 3)
#     if dose is not None:
#         item['dose'] = round(dose, 2)
#     else:
#         item['dose'] = 'none'
#     response = jsonify({'result': item})
#     response.headers.add('Access-Control-Allow-Origin', '*')
#     return response
#
#


# def get_fft_image(name: str):
#     folder = r"%s/FFTs/" % BASE_PATH
#     return download_png(name, folder)
#
#
# def get_image_thumbnail(name: str):
#     folder = r"%s/images/" % BASE_PATH
#     return download_png(name, folder)


# def download_png(name, folder):
#     response = send_file(folder + name + '.png', mimetype='image/png')
#     response.headers.add('Access-Control-Allow-Origin', '*')
#     return response


