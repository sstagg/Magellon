import glob
import os

from flask import request, jsonify, send_file
from pydantic import BaseModel

from app import app, magellonApiTag
from lib import mgDatabase
from services.helper import get_response_image, format_data_by_ext




class FFTImageQuery(BaseModel):
    name: str


class StackImagesQuery(BaseModel):
    ext: str


class ImageByThumbnailQuery(BaseModel):
    name: str





@app.get('/get_images', tags=[magellonApiTag])
def get_images():
    encoded_images = []
    data = []

    root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/thumbnails/"

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
        shortName = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]  # get image name
        item['name'] = shortName
        item['encoded_image'] = get_response_image(filename)
        item['ext'] = shortName.split("_")[5] if len(shortName.split("_")) > 5 else "misc"
        data.append(item)

    res = format_data_by_ext(data)
    response = jsonify({'result': res})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.get('/get_image_by_thumbnail', tags=[magellonApiTag])
def get_image_by_thumbnail(query: ImageByThumbnailQuery):
    args = request.args
    name = args.get('name')

    root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/images/"

    response = send_file(root_dir + name + '.png', mimetype='image/png')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.get('/get_images_by_stack', tags=[magellonApiTag])
def get_images_by_stack(query: StackImagesQuery):
    args = request.args
    ext = args.get('ext')

    encoded_images = []
    data = []
    ''' path contains list of mrc thumbnails '''
    root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/thumbnails/"

    for filename in glob.iglob(root_dir + '*.png', recursive=True):
        item = {}
        shortName = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]  # get image name
        item['name'] = shortName
        item['ext'] = shortName.split("_")[5] if len(shortName.split("_")) > 5 else "misc"
        if ext == item['ext']:
            item['encoded_image'] = get_response_image(filename)
            data.append(item)

    res = format_data_by_ext(data)
    response = jsonify({'result': res})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


@app.get('/get_fft_image', tags=[magellonApiTag])
def get_fft_image(query: FFTImageQuery):
    args = request.args
    name = args.get('name')

    root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/FFTs/"

    response = send_file(root_dir + name + '.png', mimetype='image/png')
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response
