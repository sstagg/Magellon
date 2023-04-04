import glob
import os

from starlette.responses import FileResponse, JSONResponse

from config import BASE_PATH
from models.sqlalchemy_models import Image
from services.helper import get_response_image, format_data_by_ext


def get_images():
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


# def get_image_by_stack(request: Request):
def get_image_by_stack(ext: str):
    # ext = request.query_params.get('ext')
    data = []
    ''' path contains list of mrc thumbnails '''
    root_dir = f"{BASE_PATH}/thumbnails/"
    for filename in glob.iglob(root_dir + '*.png', recursive=True):
        item = {}
        shortName = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]  # get image name
        item['name'] = shortName
        item['ext'] = shortName.split("_")[5] if len(shortName.split("_")) > 5 else "misc"
        if ext == item['ext']:
            item['encoded_image'] = get_response_image(filename)
            data.append(item)
    res = format_data_by_ext(data)
    return {'result': res}


def get_image_data(image: Image):
    if not image:
        return {"message": "Image not found."}
    result = {
        "filename": image.Name,
        "defocus": round(float(image.defocus) * 1.e6, 2),
        "PixelSize": round(float(image.pixelSizeX), 3),
        "mag": image.mag,
        "dose": round(image.dose, 2) if image.dose is not None else "none",
    }
    return {'result': result}


def get_image_thumbnail(name: str):
    folder = f"{BASE_PATH}/images/"
    return download_png(name, folder)


async def get_fft_image(name: str):
    folder = f"{BASE_PATH}/FFTs/"
    return await download_png(name, folder)


async def download_png(name: str, folder: str) -> FileResponse:
    file_path = folder + name + '.png'
    return FileResponse(file_path, media_type='image/png')
