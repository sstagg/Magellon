from datetime import datetime
from uuid import UUID
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class Camera:
    dimension_x: int
    dimension_y: int
    binning_x: int
    binning_y: int
    offset_x: int
    offset_y: int
    exposure_time: int
    exposure_type: str
    pixel_size_x: str
    pixel_size_y: str
    energy_filtered: bool


@dataclass
class Scope:
    mag: int
    spotSize: int
    intensity: float
    shiftX: float
    shiftY: float
    beamShiftX: float
    beamShiftY: float
    focus: float
    defocus: float
    condenserX: float
    condenserY: float
    objectiveX: float
    objectiveY: float


@dataclass
class Image:
    id: UUID
    name: str
    path: str
    mag: int
    defocus: int
    pixsize: float
    dose: None
    microscope: Scope
    camera: Camera
    fft_image: str
    fft_path: str
    ctf_name: str
    ctf_path: str
    labels: str
    pixels: int
    preset: int


@dataclass
class Session:
    id: Optional[UUID]
    name: str
    created_on: datetime
    updated_on: datetime
    user: int
    images: List[Image]


@dataclass
class Project:
    name: str
    description: str
    session: List[Session]
