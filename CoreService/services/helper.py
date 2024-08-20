import base64
import io
import json
import os
import re
import time
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

def get_parent_name(child_name):
    split_name = child_name.split('_')
    # if split_name[-1] == 'v01':
    if re.search(r'[vV]([0-9][0-9])', split_name[-1]):
        parent_name = '_'.join(split_name[:-2])
    else:
        parent_name = '_'.join(split_name[:-1])
    # Join the parts back together with underscores and return
    return parent_name

def get_image_base64(base64_string: str):
    # Decode the base64 string into binary data
    binary_data = base64.b64decode(base64_string)

    # Create a BytesIO object with the binary data
    bytes_io = io.BytesIO(binary_data)

    # Return the FileResponse with BytesIO object as content
    return StreamingResponse(io.BytesIO(binary_data), media_type='image/png')


def custom_replace(input_string, replace_type, replace_pattern, replace_with):
    """
    Function to perform various types of string replacement based on the specified replace_type.

    Parameters:
        input_string (str): The input string to be modified.
        replace_type (str): Type of replacement. Can be 'none', 'normal', or 'regex'.
        replace_pattern (str): Pattern to search for in the input string.
        replace_with (str): String to replace the replace_pattern with.

    Returns:
        str: The modified string after replacement.
    """
    if replace_type == 'none':
        return input_string

    elif replace_type == 'standard':
        return input_string.replace(replace_pattern, replace_with)

    elif replace_type == 'regex':
        return re.sub(replace_pattern, replace_with, input_string)

    else:
        raise ValueError("Invalid replace_type. Use 'none', 'normal', or 'regex'.")


def delete_old_empty_directories(parent_dir):
    current_time = time.time()

    # Walk through the directory tree
    for dirpath, dirnames, filenames in os.walk(parent_dir, topdown=False):
        # Check if the directory is empty
        if not os.listdir(dirpath):
            # Check the last modification time
            mod_time = os.path.getmtime(dirpath)
            if current_time - mod_time > 5 * 60:  # 5 minutes in seconds
                try:
                    os.rmdir(dirpath)
                    print(f"Deleted empty directory: {dirpath}")
                except Exception as e:
                    print(f"Failed to delete {dirpath}: {e}")