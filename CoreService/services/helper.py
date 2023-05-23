import io
import json
from _operator import itemgetter
from base64 import b64encode
from itertools import groupby
from uuid import UUID

from PIL import Image


def format_data_by_ext(data):
    sortedRes = []
    response = []
    # sort data by 'ext' key.
    sortedRes = sorted(data, key=key_func)

    for key, value in groupby(sortedRes, key_func):
        item = {}
        imgGroupByExt = []
        item['ext'] = key

        for image in value:
            imgGroupByExt.append(image)

        sorted_imgGroupByExt = sorted(imgGroupByExt, key=itemgetter('name'), reverse=True)

        item['images'] = sorted_imgGroupByExt
        response.append(item)
    return response


def get_response_image(image_path):
    pil_img = Image.open(image_path, mode='r')  # reads the PIL image
    byte_arr = io.BytesIO()
    pil_img.save(byte_arr, format='PNG')  # convert the PIL image to byte array
    encoded_img = b64encode(byte_arr.getvalue()).decode('ascii')  # encode as base64
    return encoded_img


def key_func(k):
    return k['ext']


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)