import base64
import io
import json
from _operator import itemgetter
from base64 import b64encode
from itertools import groupby
from uuid import UUID

from PIL import Image
from starlette.responses import StreamingResponse


# def format_data_by_ext(data):
#     response = []
#     # sort data by 'ext' key.
#     for key, value in groupby(sorted(data, key=key_func), key_func):
#         response.append({'ext': key, 'images': sorted(list(value), key=itemgetter('name'), reverse=True)})
#     return response

def format_data_by_ext(data):
    response = [
        {'ext': key, 'images': sorted(list(value), key=itemgetter('name'), reverse=True)}
        for key, value in groupby(sorted(data, key=lambda k: k['ext']), key=lambda k: k['ext'])
    ]
    return response


def key_func(k):
    return k['ext']


def get_response_image(image_path):
    pil_img = Image.open(image_path, mode='r')  # reads the PIL image
    byte_arr = io.BytesIO()
    pil_img.save(byte_arr, format='PNG')  # convert the PIL image to byte array
    encoded_img = b64encode(byte_arr.getvalue()).decode('ascii')  # encode as base64
    return encoded_img


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


def get_image_base64(base64_string: str):
    # Decode the base64 string into binary data
    binary_data = base64.b64decode(base64_string)

    # Create a BytesIO object with the binary data
    bytes_io = io.BytesIO(binary_data)

    # Return the FileResponse with BytesIO object as content
    return StreamingResponse(io.BytesIO(binary_data), media_type='image/png')
