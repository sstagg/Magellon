from enum import Enum

from pydantic import BaseModel, Field, Json, ValidationInfo, field_validator
from typing import Optional, List
import uuid


class SlackMessage(BaseModel):
    text: str
    channel: Optional[str] = None


class AtlasDto(BaseModel):
    oid: uuid.UUID = Field(None, description='Atlas UUID')
    name: str = Field(None, min_length=2, max_length=30, description='Atlas Name')
    meta: str = Field(None, description='Atlas Meta')

    # model_config = ConfigDict(from_attributes=True)
    class Config:
        from_attributes = True


class CameraDto(BaseModel):
    oid: uuid.UUID = Field(None, description='Camera UUID')
    name: str = Field(None, min_length=2, max_length=30, description='Camera Name')
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')

    # model_config = ConfigDict(from_attributes=True)
    class Config:
        from_attributes = True


class ImageMetaDataCategoryDto(BaseModel):
    oid: uuid.UUID = Field(None, description='ImageMetaDataCategory UUID')
    name: str = Field(None, min_length=2, max_length=30, description='ImageMetaDataCategory Name')
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')

    # model_config = ConfigDict(from_attributes=True)
    class Config:
        from_attributes = True


class SessionDto(BaseModel):
    oid: uuid.UUID = Field(None, description='Session UUID')
    name: str = Field(None, min_length=2, max_length=30, description='Camera Name')
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')

    # model_config = ConfigDict(from_attributes=True)
    class Config:
        from_attributes = True


class ImageDtoBase(BaseModel):
    name: Optional[str] = None
    # name: str = Field(None, min_length=2, max_length=30, description='Image Name')
    original: Optional[bytes]
    aligned: Optional[bytes]
    fft: Optional[bytes]
    ctf: Optional[bytes]
    path: Optional[str] = None
    parent: Optional[uuid.UUID] = None
    session: uuid.UUID
    atlas: uuid.UUID
    magnification: Optional[int]
    dose: Optional[float]
    focus: Optional[float]
    defocus: Optional[float]
    spot_size: Optional[int]
    intensity: Optional[float]
    shift_x: Optional[float]
    shift_y: Optional[float]
    beam_shift_x: Optional[float]
    beam_shift_y: Optional[float]
    reset_focus: Optional[int]
    screen_current: Optional[int]
    beam_bank: Optional[str]
    condenser_x: Optional[float]
    condenser_y: Optional[float]
    objective_x: Optional[float]
    objective_y: Optional[float]
    dimension_x: Optional[int]
    dimension_y: Optional[int]
    binning_x: Optional[int]
    binning_y: Optional[int]
    offset_x: Optional[int]
    offset_y: Optional[int]
    exposure_time: Optional[float]
    exposure_type: Optional[int]
    pixel_size_x: Optional[float]
    pixel_size_y: Optional[float]
    atlas_delta_row: Optional[float]
    atlas_delta_column: Optional[float]
    energy_filtered: Optional[bool]
    GCRecord: Optional[int] = None


class ImageDtoCreate(ImageDtoBase):
    pass


class ImageDtoUpdate(ImageDtoBase):
    pass


class ImageDtoInDBBase(ImageDtoBase):
    oid: uuid.UUID = Field(description='Image UUID')

    class Config:
        from_attributes = True


class ImageDtoInDB(ImageDtoInDBBase):
    OptimisticLockField: int
    GCRecord: Optional[int]


class ImageDto(ImageDtoInDBBase):
    pass


class ImageDtoWithParent(ImageDto):
    parent1: Optional[ImageDto] = None


class MySQLConnectionSettings(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str

class ReplaceType(str, Enum):
    NONE = "none"
    STANDARD = "standard"
    REGEX = "regex"


class ImportJobBase(BaseModel):
    job_id: Optional[uuid.UUID] = None
    magellon_project_name: str
    magellon_session_name: str
    camera_directory: Optional[str] = None  # for copying frames
    session_name: Optional[str] = None
    if_do_subtasks: Optional[bool] = True
    copy_images: Optional[bool] = False
    retries: Optional[int] = None
    task_list: Optional[List] = None  # List to store the tasks List[LeginonFrameTransferTaskDto]
    replace_type: ReplaceType = ReplaceType.NONE
    replace_pattern: Optional[str] = None
    replace_with: Optional[str] = None

    @field_validator("replace_type")
    def validate_replace_type(cls, v):
        if v not in ReplaceType.__members__.values():
            raise ValueError(f"Invalid replace_type: {v}. Valid options are: {', '.join(ReplaceType.__members__.keys())}")
        return v

class ImportTaskDto(BaseModel):
    task_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    task_alias: Optional[str] = None
    file_name: Optional[str] = None
    image_id: Optional[uuid.UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None
    job_dto: ImportJobBase
    status: Optional[int] = None
    pixel_size: Optional[float] = None
    acceleration_voltage: Optional[float] = None
    spherical_aberration: Optional[float] = None
    amplitude_contrast:Optional[float] = 0.07
    size_of_amplitude_spectrum: Optional[int] = 512
    minimum_resolution: Optional[int] = 30
    maximum_resolution: Optional[int] = 5
    minimum_defocus: Optional[int] = 5000
    maximum_defocus: Optional[int] = 50000
    defocus_search_step: Optional[int] = 100


class LeginonFrameTransferJobBase(ImportJobBase):

    leginon_mysql_host: Optional[str] = None
    leginon_mysql_port: Optional[int]
    leginon_mysql_db: Optional[str] = None
    leginon_mysql_user: Optional[str] = None
    leginon_mysql_pass: Optional[str] = None

    replace_type: str = "none"
    replace_pattern: Optional[str] = None
    replace_with: Optional[str] = None

    @field_validator("replace_type")
    def validate_replace_type(cls, v: str, info: ValidationInfo) -> str:
        """
        Validates the replace_type value.
        """
        valid_types = ["standard", "none", "regex"]
        if v not in valid_types:
            raise ValueError(f"Invalid replace_type: {v}. Valid options are: {', '.join(valid_types)}")
        return v


class LeginonFrameTransferJobDto(LeginonFrameTransferJobBase):
    target_directory: Optional[str] = None  # should be removed, it is base directory + magellon_session_name name




class LeginonFrameTransferTaskDto(BaseModel):
    task_id: uuid.UUID
    task_alias: Optional[str] = None
    file_name: Optional[str] = None
    image_id: Optional[uuid.UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None
    job_dto: LeginonFrameTransferJobDto
    status: Optional[int] = None
    pixel_size: Optional[float] = None
    acceleration_voltage: Optional[float] = None
    spherical_aberration: Optional[float] = None
    amplitude_contrast:Optional[float] = 0.07
    size_of_amplitude_spectrum: Optional[int] = 512
    minimum_resolution: Optional[int] = 30
    maximum_resolution: Optional[int] = 5
    minimum_defocus: Optional[int] = 5000
    maximum_defocus: Optional[int] = 50000
    defocus_search_step: Optional[int] = 100


class LeginonImageDto(BaseModel):
    defocus: float
    mag: int
    filename: str
    pixelsize: float
    dose: float


class MicrographSetDto(BaseModel):
    oid: Optional[uuid.UUID] = None
    parent_name: Optional[str] = None
    name: Optional[str] = None
    encoded_image: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    level: Optional[int] = None


class ImageDto(BaseModel):
    oid: Optional[uuid.UUID] = None
    name: Optional[str] = None
    defocus: Optional[float] = None
    dose: Optional[float] = None
    mag: Optional[float] = None
    pixelSize: Optional[float] = None
    parent_id: Optional[uuid.UUID] = None
    session_id: Optional[uuid.UUID] = None
    children_count: Optional[int] = None


class ImageMetaDataDto(BaseModel):
    oid: Optional[uuid.UUID] = None
    image_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    # created_on: Optional[datetime] = None
    data: Optional[str] = None
    OptimisticLockField: Optional[int] = None
    GCRecord: Optional[int] = None
    type: Optional[int] = None
    data_json: Optional[list] = None


class ParticlePickingDto(BaseModel):
    oid: uuid.UUID
    image_id: uuid.UUID
    name: Optional[str] = None
    data: Optional[str] = None
    data_json: Optional[Json] = None
    status: Optional[int] = None
    type: Optional[int] = None



class EPUFrameTransferJobBase(BaseModel):
    magellon_project_name: "EPU"
    magellon_session_name: "epu_session"
    camera_directory: Optional[str] = None  # for copying frames
    epu_session_name: Optional[str] = None
    if_do_subtasks: Optional[bool] = True
    copy_images: Optional[bool] = False
    retries: Optional[int] = None

    replace_type: str = "none"
    replace_pattern: Optional[str] = None
    replace_with: Optional[str] = None

    @field_validator("replace_type")
    def validate_replace_type(cls, v: str, info: ValidationInfo) -> str:
        """
        Validates the replace_type value.
        """
        valid_types = ["standard", "none", "regex"]
        if v not in valid_types:
            raise ValueError(f"Invalid replace_type: {v}. Valid options are: {', '.join(valid_types)}")
        return v
