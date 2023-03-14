from sqlalchemy.ext.declarative import declarative_base
from flask_sqlalchemy import SQLAlchemy
from dataclasses import asdict
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import relationship

Base = declarative_base()

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Image(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    mag = db.Column(db.Integer, nullable=False)
    defocus = db.Column(db.Integer, nullable=False)
    pixsize = db.Column(db.Float, nullable=False)
    dose = db.Column(db.Float)
    dimension_x = db.Column(db.Integer, nullable=False)
    dimension_y = db.Column(db.Integer, nullable=False)
    binning_x = db.Column(db.Integer, nullable=False)
    binning_y = db.Column(db.Integer, nullable=False)
    offset_x = db.Column(db.Integer, nullable=False)
    offset_y = db.Column(db.Integer, nullable=False)
    exposure_time = db.Column(db.Integer, nullable=False)
    exposure_type = db.Column(db.String(255), nullable=False)
    pixel_size_x = db.Column(db.String(255), nullable=False)
    pixel_size_y = db.Column(db.String(255), nullable=False)
    energy_filtered = db.Column(db.Boolean, nullable=False)
    created_on = db.Column(db.DateTime, default=datetime.utcnow)
    updated_on = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def from_dataclass(cls, image):
        image_dict = asdict(image)
        image_dict['id'] = str(uuid4())
        return cls(**image_dict)


class Session(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100))
    created_on = db.Column(db.DateTime)
    updated_on = db.Column(db.DateTime)
    user = db.Column(db.Integer)
    images = relationship('Image', backref='session')


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    description = db.Column(db.String(255))
    sessions = relationship('Session', backref='project')


class Camera(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dimension_x = db.Column(db.Integer)
    dimension_y = db.Column(db.Integer)
    binning_x = db.Column(db.Integer)
    binning_y = db.Column(db.Integer)
    offset_x = db.Column(db.Integer)
    offset_y = db.Column(db.Integer)
    exposure_time = db.Column(db.Integer)
    exposure_type = db.Column(db.String(50))
    pixel_size_x = db.Column(db.Float)
    pixel_size_y = db.Column(db.Float)
    energy_filtered = db.Column(db.Boolean)


class Image(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100))
    path = db.Column(db.String(255))
    mag = db.Column(db.Integer)
    defocus = db.Column(db.Integer)
    pixsize = db.Column(db.Float)
    dose = db.Column(db.Integer)
    fft_image = db.Column(db.String(255))
    fft_path = db.Column(db.String(255))
    ctf_name = db.Column(db.String(255))
    ctf_path = db.Column(db.String(255))
    labels = db.Column(db.String(255))
    pixels = db.Column(db.Integer)
    preset = db.Column(db.Integer)
    dimension_x = db.Column(db.Integer)
    dimension_y = db.Column(db.Integer)
    binning_x = db.Column(db.Integer)
    binning_y = db.Column(db.Integer)
    offset_x = db.Column(db.Integer)
    offset_y = db.Column(db.Integer)
    exposure_time = db.Column(db.Integer)
    exposure_type = db.Column(db.String(50))
    pixel_size_x = db.Column(db.Float)
    pixel_size_y = db.Column(db.Float)
    energy_filtered = db.Column(db.Boolean)
    session_id = db.Column(db.String(36), db.ForeignKey('session.id'))
    microscope = relationship('Scope')


class Scope(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mag = db.Column(db.Integer)
    spotSize = db.Column(db.Integer)
    intensity = db.Column(db.Float)
    shiftX = db.Column(db.Float)
    shiftY = db.Column(db.Float)
    beamShiftX = db.Column(db.Float)
    beamShiftY = db.Column(db.Float)
    focus = db.Column(db.Float)
    defocus = db.Column(db.Float)
    condenserX = db.Column(db.Float)
    condenserY = db.Column(db.Float)
    objectiveX = db.Column(db.Float)
    objectiveY = db.Column(db.Float)
    image_id = db.Column(db.String(36), db.ForeignKey('image.id'))
