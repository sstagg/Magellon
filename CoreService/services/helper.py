import io
import re
from _operator import itemgetter
from base64 import b64encode
from itertools import groupby

from PIL import Image


def format_data_by_ext(data):
    response = [
        {'ext': key, 'images': sorted(list(value), key=itemgetter('name'), reverse=True)}
        for key, value in groupby(sorted(data, key=lambda k: k['ext']), key=lambda k: k['ext'])
    ]
    return response


def get_response_image(image_path):
    pil_img = Image.open(image_path, mode='r')
    byte_arr = io.BytesIO()
    pil_img.save(byte_arr, format='PNG')
    encoded_img = b64encode(byte_arr.getvalue()).decode('ascii')
    return encoded_img


def get_parent_name(child_name):
    split_name = child_name.split('_')
    if re.search(r'[vV]([0-9][0-9])', split_name[-1]):
        parent_name = '_'.join(split_name[:-2])
    else:
        parent_name = '_'.join(split_name[:-1])
    return parent_name