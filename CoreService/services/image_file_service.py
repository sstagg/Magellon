import glob
import os
from typing import Any

from starlette.responses import FileResponse

from config import THUMBNAILS_DIR
from models.sqlalchemy_models import Image
from services.helper import get_response_image, format_data_by_ext


def get_images() -> dict[str, Any]:
    data = []  # Initialize an empty list to store image data
    filename_list = os.listdir(THUMBNAILS_DIR)  # Get the list of filenames in the specified directory

    parent_file_ext = set()  # Store distinct parent file extensions

    # Identify parent file extensions present in the filenames
    for filename in filename_list:
        if len(filename.split("_")) > 6:
            parent_file_ext.add(filename.split("_")[5])  # Consider the sixth section as parent file extension
        else:
            parent_file_ext.add('misc')  # Assign 'misc' as parent file extension for filenames with fewer sections

    stack_3_images_list = set()  # Store filenames of three representative images for each parent file extension

    # Find representative images for each parent file extension
    for ext in parent_file_ext:
        count = 0  # Track the number of representative images found
        for filename in filename_list:
            # Check if filename matches the criteria for a representative image
            if (ext in filename) and len(filename.split("_")) >= 6 and (
                    filename.endswith(ext + '_TIMG.png')) and count == 0:
                stack_3_images_list.add(filename)  # Add the filename to the set
                count += 1

        # If fewer than three representative images found, add other matching filenames
        for filename in filename_list:
            if (ext in filename) and not filename.endswith(ext + '_TIMG.png') and count < 3:
                stack_3_images_list.add(filename)  # Add the filename to the set
                count += 1

    # Iterate through the filenames and process the selected images and append them to Data
    for file_path in glob.iglob(THUMBNAILS_DIR + '*.png', recursive=True):
        # if filename.rsplit("/", 1)[1] not in stack_3_images_list:
        if os.path.basename(file_path) not in stack_3_images_list:
            continue  # Skip filenames not present in the representative images set

        item = {}  # Create a dictionary to store image data
        # short_name = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]  # Get the image name
        short_name = os.path.splitext(os.path.basename(file_path))[0]  # Get the image name without extension

        item['name'] = short_name  # Add the image name to the dictionary
        item['encoded_image'] = get_response_image(file_path)  # Get the encoded image data
        item['ext'] = short_name.split("_")[5] if len(
            short_name.split("_")) > 5 else "misc"  # Extract the parent file extension
        data.append(item)  # Add the image data dictionary to the list

    res = format_data_by_ext(data)  # Further process the data based on the file extensions

    # Return a JSON response with the formatted data and headers
    # return JSONResponse(content={'result': res}, headers={'Access-Control-Allow-Origin': '*'})
    return {'result': res}


# def get_image_by_stack(request: Request):
def get_image_by_stack(ext: str):
    # ext = request.query_params.get('ext')
    data = []
    ''' path contains list of mrc thumbnails '''
    for filename in glob.iglob(THUMBNAILS_DIR + '*.png', recursive=True):
        item = {}
        short_name = os.path.splitext(os.path.basename(filename))[0]  # get image name
        item['name'] = short_name
        item['ext'] = short_name.split("_")[5] if len(short_name.split("_")) > 5 else "misc"
        if ext == item['ext']:
            item['encoded_image'] = get_response_image(filename)
            data.append(item)
    res = format_data_by_ext(data)
    return {'result': res}


def get_image_data(image: Image):
    if not image:
        return {"message": "Image not found."}
    result = {
        "filename": image.name,
        "defocus": round(float(image.defocus) * 1.e6, 2),
        "PixelSize": round(float(image.pixel_size) * image.binning_x, 3),
        "mag": image.magnification,
        "dose": round(image.dose, 2) if image.dose is not None else "none",
    }
    return {'result': result}


# async def get_fft_image(name: str):
#     return await download_png(name, FFT_DIR)


async def download_png(name: str, folder: str) -> FileResponse:
    file_path = f"{folder}{name}.png"
    return FileResponse(file_path, media_type='image/png')
