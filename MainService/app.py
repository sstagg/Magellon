#!/usr/bin/env python
# encoding: utf-8
import random
import subprocess
import uuid
from uuid import uuid4
import logging

from flask import jsonify
from flask_openapi3 import OpenAPI
from flask_openapi3 import Info, Tag
from flask_restful import Api
from flask_sqlalchemy import SQLAlchemy
from pydantic import BaseModel, Field

from typing import Optional, List
from sqlalchemy.exc import SQLAlchemyError

from config import DB_USER, DB_PASSWORD, DB_HOST, DB_NAME, DB_Driver, DB_Port
from models.models import Camera, metadata
from services.db_service import DbService

from services.image_service import ImageMetadataQuery, FFTImageQuery, StackImagesQuery, ImageByThumbnailQuery, \
    get_images, get_image_thumbnail, get_image_by_stack, get_image_data, get_fft_image
from services.motioncore_service import Motioncor2Input, MotioncoreService
# from views.fft_view import fft_view

from views.file_rest import transfer_file_and_dir, TransferInput
# Register the home blueprint
from views.home import home_bp
from views.math_rest import Math

info = Info(title="Magellon Main Service API", version="1.0.0")
app = OpenAPI(__name__, info=info)

app.config['SQLALCHEMY_DATABASE_URI'] = f'{DB_Driver}://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_Port}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# # Configure the SQLAlchemy engine and Session
# engine = create_engine(f'mysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}')
# Session = sessionmaker(bind=engine)

# Enable SQLAlchemy logging for debugging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

api = Api(app)
magellonApiTag = Tag(name="Magellon", description="Magellon Main Service")

app.register_blueprint(home_bp)
# app.register_blueprint(fft_view)


@app.get('/create-database', tags=[magellonApiTag], description='creates database structure')
def create_schema():
    db_service = DbService(db)
    # db_service.create_app_database()
    # db_service.create_all_tables()

    metadata.create_all(bind=db.engine)

    return jsonify({
        'code': 201,
        'status': 'success',
        'message': 'Datbase Structure created',
    }), 201


class CameraQuery(BaseModel):
    oid: uuid.UUID = Field(description='Camera UUID')
    name: str = Field(min_length=2, max_length=30, description='Camera Name')
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')


@app.post('/camera', tags=[magellonApiTag], description='Inserts a new camera')
def insert_camera(body: CameraQuery):
    num = random.randint(1, 1000)
    # create a new camera
    new_camera = Camera(Oid=uuid4(), name=f'my_camera {num}')
    new_camera.Oid = body.oid
    new_camera.name = body.name

    # add the camera to the database
    db.session.add(new_camera)
    db.session.commit()

    return jsonify({
        'code': 201,
        'status': 'success',
        'message': 'Camera created',
        'data': {
            'id': (str(new_camera.Oid)),
            'name': new_camera.name,
        }
    }), 201


class GetSoloObjectQuery(BaseModel):
    oid: uuid.UUID


@app.get('/camera', tags=[magellonApiTag], description='gets a camera')
def get_camera(query: GetSoloObjectQuery):
    try:
        # string_uuid = str(uuid.UUID(bytes=camera.Oid))
        # theUuid = uuid.UUID(query.oid)
        # Attempt to retrieve the camera with the given ID or UUID
        camera = db.session.query(Camera).filter(Camera.Oid == query.oid).one()
        if camera is None:
            # Camera not found, return error message
            return jsonify({'error': 'Camera not found'}), 404
        else:
            # Camera found, return its properties
            return jsonify({
                'Oid': str(camera.Oid),
                'name': camera.name,
                'OptimisticLockField': camera.OptimisticLockField,
                'GCRecord': camera.GCRecord
            }), 200

    except SQLAlchemyError:
        # If an error occurs, return a 404 error with a corresponding message
        return jsonify({'error': f"Camera with ID or UUID '{str(query.oid)}' not found"}), 404
    # finally:
    #     return jsonify({'error': f"Camera with ID or UUID '{theUuid}' not found"}), 404


@app.post('/transfer', tags=[magellonApiTag],
          description='Transfer files and directories from source path to target path.')
def transfer_files1(body: TransferInput):
    return transfer_file_and_dir(body)


@app.get('/get_images', tags=[magellonApiTag])
def get_images_route():
    return get_images()


@app.get('/get_image_by_thumbnail', tags=[magellonApiTag])
def get_image_by_thumbnail_route(query: ImageByThumbnailQuery):
    return get_image_thumbnail()


@app.get('/get_images_by_stack', tags=[magellonApiTag])
def get_images_by_stack_route(query: StackImagesQuery):
    return get_image_by_stack()


@app.get('/get_fft_image', tags=[magellonApiTag])
def get_fft_image_route(query: FFTImageQuery):
    return get_fft_image()


@app.get('/get_image_data', tags=[magellonApiTag])
def get_image_data_route(query: ImageMetadataQuery):
    return get_image_data()


@app.get('/motioncor2', methods=['POST'])
def run_motioncor2_route(body: Motioncor2Input):
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
