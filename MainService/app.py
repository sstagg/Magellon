#!/usr/bin/env python
# encoding: utf-8

from flask_openapi3 import Info, Tag, OpenAPI
from flask_restful import Api

from rest.mathRest import Math
from services.ImageHelper import ImageMetadataQuery, FFTImageQuery, StackImagesQuery, ImageByThumbnailQuery, getImages, \
    getImageByThumbnail, getImageByStack, getImageData, getFftImage

info = Info(title="Magellon Main Service API", version="1.0.0")
app = OpenAPI(__name__, info=info)
api = Api(app)
magellonApiTag = Tag(name="Magellon", description="Magellon Main Service")


@app.get('/', tags=[magellonApiTag])
def home():
    return 'Welcome to magellon main service <p>For api please go to <a href="/openapi">OpenApi</a></p>'


@app.get('/get_images', tags=[magellonApiTag])
def get_images():
    return getImages()


@app.get('/get_image_by_thumbnail', tags=[magellonApiTag])
def get_image_by_thumbnail(query: ImageByThumbnailQuery):
    return getImageByThumbnail()


@app.get('/get_images_by_stack', tags=[magellonApiTag])
def get_images_by_stack(query: StackImagesQuery):
    return getImageByStack()


@app.get('/get_fft_image', tags=[magellonApiTag])
def get_fft_image(query: FFTImageQuery):
    return getFftImage()


@app.get('/get_image_data', tags=[magellonApiTag])
def get_image_data(query: ImageMetadataQuery):
    return getImageData()


# api.add_resource(Math, '/math/<int:num1>/<int:num2>/<string:operation>')
api.add_resource(Math, '/add/<int:num1>/<int:num2>', endpoint='add')
# api.add_resource(Math, '/multiply/<int:num1>/<int:num2>', endpoint='multiply')

if __name__ == "__main__":
    app.run(debug=True)
