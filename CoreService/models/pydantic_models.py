from pydantic import BaseModel, Field
from typing import Optional, List
import uuid


class CameraDto(BaseModel):
    Oid: uuid.UUID = Field(description='Camera UUID')
    name: str = Field(None, min_length=2, max_length=30, description='Camera Name')
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')

    class Config:
        orm_mode = True


class ImageDto(BaseModel):
    Oid: uuid.UUID = Field(description='Image UUID')
    Name: str = Field(None, min_length=2, max_length=30, description='Image Name')
    original: Optional[bytes]
    aligned: Optional[bytes]
    fft: Optional[bytes]
    ctf: Optional[bytes]
    path: Optional[str]
    parent: Optional[str]
    session: Optional[str]
    mag: Optional[int]
    focus: Optional[float]
    defocus: Optional[float]
    spotSize: Optional[int]
    intensity: Optional[float]
    shiftX: Optional[float]
    shiftY: Optional[float]
    beamShiftX: Optional[float]
    beamShiftY: Optional[float]
    resetFocus: Optional[int]
    screenCurrent: Optional[int]
    beamBank: Optional[str]
    condenserX: Optional[float]
    condenserY: Optional[float]
    objectiveX: Optional[float]
    objectiveY: Optional[float]
    dimensionX: Optional[int]
    dimensionY: Optional[int]
    binningX: Optional[int]
    binningY: Optional[int]
    offsetX: Optional[int]
    offsetY: Optional[int]
    exposureTime: Optional[float]
    exposureType: Optional[int]
    pixelSizeX: Optional[float]
    pixelSizeY: Optional[float]
    energyFiltered: Optional[bool]
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')

    class Config:
        orm_mode = True
