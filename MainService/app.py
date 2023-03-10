#!/usr/bin/env python
# encoding: utf-8
import subprocess

from flask import jsonify
from flask_openapi3 import OpenAPI
from flask_openapi3 import Info, Tag
from flask_restful import Api
from pydantic import BaseModel, Field

from controllers.file_rest import TransferInput, transfer_file_and_dir
from controllers.math_rest import Math
from services.image_service import ImageMetadataQuery, FFTImageQuery, StackImagesQuery, ImageByThumbnailQuery, \
    get_images, get_image_thumbnail, get_image_by_stack, get_image_data, get_fft_image
from services.motioncore_service import Motioncor2Input, MotioncoreService
# Register the home blueprint
from views.home import home_bp

info = Info(title="Magellon Main Service API", version="1.0.0")
app = OpenAPI(__name__, info=info)
api = Api(app)
magellonApiTag = Tag(name="Magellon", description="Magellon Main Service")

app.register_blueprint(home_bp)


class NotFoundResponse(BaseModel):
    code: int = Field(-1, description="Status Code")
    message: str = Field("Resource not found!", description="Exception Information")


@app.post('/transfer', tags=[magellonApiTag],
          description='Transfer files and directories from source path to target path.')
def transfer_files1(body: TransferInput):
    return transfer_file_and_dir(body)


# @app.get('/', tags=[magellonApiTag])
# def home():
#     return 'Welcome to magellon main service <p>For api please go to <a href="/openapi">OpenApi</a></p>'


@app.get('/get_images', tags=[magellonApiTag])
def get_images():
    return get_images()


@app.get('/get_image_by_thumbnail', tags=[magellonApiTag])
def get_image_by_thumbnail(query: ImageByThumbnailQuery):
    return get_image_thumbnail()


@app.get('/get_images_by_stack', tags=[magellonApiTag])
def get_images_by_stack(query: StackImagesQuery):
    return get_image_by_stack()


@app.get('/get_fft_image', tags=[magellonApiTag])
def get_fft_image(query: FFTImageQuery):
    return get_fft_image()


@app.get('/get_image_data', tags=[magellonApiTag])
def get_image_data(query: ImageMetadataQuery):
    return get_image_data()


@app.get('/motioncor2', methods=['POST'])
def run_motioncor2(body: Motioncor2Input):
    # Run motioncor2 using MotioncoreService
    motioncore_service = MotioncoreService()
    try:
        output = motioncore_service.run_motioncor2(body.mrc_files,
                                                   body.dose_per_frame,
                                                   body.patch_size,
                                                   body.binning)
        return jsonify({'output': output.decode()}), 200
    except subprocess.CalledProcessError as e:
        return jsonify({'error': e.output.decode()}), 500


# api.add_resource(Math, '/math/<int:num1>/<int:num2>/<string:operation>')
api.add_resource(Math, '/add/<int:num1>/<int:num2>', endpoint='add')
# api.add_resource(Math, '/multiply/<int:num1>/<int:num2>', endpoint='multiply')

if __name__ == "__main__":
    app.run(debug=False)
