from flask import request, jsonify
from pydantic import BaseModel

from lib import mgDatabase


class ImageMetadataQuery(BaseModel):
    name: str


class FFTImageQuery(BaseModel):
    name: str


class StackImagesQuery(BaseModel):
    ext: str


class ImageByThumbnailQuery(BaseModel):
    name: str


class ImageHelper():
    def getImageData(self, query: ImageMetadataQuery):
        args = request.args
        name = args.get('name')
        data = mgDatabase.getImageData(name)
        ''' Get pixel size in Angstroms '''
        pixelsize = mgDatabase.getPixelSize(data)
        ''' Get dose in electrons per Angstrom '''
        dose = mgDatabase.getDoseFromImageData(data)
        item = {}
        item['defocus'] = round(data['preset']['defocus'] * 1.e6, 2)
        item['mag'] = data['preset']['magnification']
        item['filename'] = data['filename']
        item['pixelsize'] = round(pixelsize, 3)
        if dose is not None:
            item['dose'] = round(dose, 2)
        else:
            item['dose'] = 'none'
        response = jsonify({'result': item})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
