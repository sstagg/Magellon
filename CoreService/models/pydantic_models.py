from pydantic import BaseModel, Field, Json, ValidationInfo, field_validator
from typing import Optional, List
import uuid


class SlackMessage(BaseModel):
    text: str
    channel: Optional[str] = None


class AtlasDto(BaseModel):
    Oid: uuid.UUID = Field(None, description='Atlas UUID')
    name: str = Field(None, min_length=2, max_length=30, description='Atlas Name')
    meta: str = Field(None, description='Atlas Meta')

    # model_config = ConfigDict(from_attributes=True)
    class Config:
        from_attributes = True


class CameraDto(BaseModel):
    Oid: uuid.UUID = Field(None, description='Camera UUID')
    name: str = Field(None, min_length=2, max_length=30, description='Camera Name')
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')

    # model_config = ConfigDict(from_attributes=True)
    class Config:
        from_attributes = True


class SessionDto(BaseModel):
    Oid: uuid.UUID = Field(None, description='Session UUID')
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
    Oid: uuid.UUID = Field(description='Image UUID')

    class Config:
        from_attributes = True


class ImageDtoInDB(ImageDtoInDBBase):
    OptimisticLockField: int
    GCRecord: Optional[int]


class ImageDto(ImageDtoInDBBase):
    pass


class ImageDtoWithParent(ImageDto):
    parent1: Optional[ImageDto] = None


# ================================================================================================
class Particlepickingjob(BaseModel):
    Oid: uuid.UUID
    name: Optional[str] = None
    description: Optional[str] = None
    # created_on: datetime
    # end_on: datetime
    user: Optional[str] = None
    project: Optional[str] = None
    msession: Optional[str] = None
    status: Optional[int]
    type: Optional[int]
    data: Optional[Json]
    # cs: Decimal
    path: Optional[str] = None
    output_dir: Optional[str] = None
    direction: Optional[int]
    image_selection_criteria: Optional[str]
    OptimisticLockField: Optional[int]
    GCRecord: Optional[int]


class ParticlepickingjobitemBase(BaseModel):
    job: uuid.UUID
    job_name: Optional[str] = None
    image: uuid.UUID
    data: Optional[Json] = None
    status: Optional[int] = None
    type: Optional[int] = None


class ParticlepickingjobDto(Particlepickingjob):
    pass


class ParticlepickingjobitemCreate(ParticlepickingjobitemBase):
    pass


class ParticlepickingjobitemUpdate(ParticlepickingjobitemBase):
    pass


class ParticlepickingjobitemInDBBase(ParticlepickingjobitemBase):
    Oid: uuid.UUID

    class Config:
        from_attributes = True


class ParticlepickingjobitemDto(ParticlepickingjobitemInDBBase):
    pass


class Particlepickingjobitem(ParticlepickingjobitemInDBBase):
    pass


class ParticlepickingjobitemInDB(ParticlepickingjobitemInDBBase):
    GCRecord: Optional[int] = None
    OptimisticLockField: Optional[int] = None


# ================================================================================================
# class LightImageDto(BaseModel):
#     name: str = Optional[str]
#
#
# class ParticlepickingjobitemResult(BaseModel):
#     JobItem: ParticlepickingjobitemDto
#     Job: ParticlepickingjobDto
#
#
# class QueryResult(BaseModel):
#     results: List[ParticlepickingjobitemResult]


# ================================================================================================
class MySQLConnectionSettings(BaseModel):
    host: str
    port: int
    user: str
    password: str
    database: str


class LeginonFrameTransferJobBase(BaseModel):
    magellon_project_name: str
    magellon_session_name: str
    camera_directory: Optional[str] = None  # for copying frames
    session_name: Optional[str] = None
    if_do_subtasks: Optional[bool] = True
    copy_images: Optional[bool] = False
    retries: Optional[int] = None

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
    job_id: Optional[uuid.UUID] = None  # should be removed
    target_directory: Optional[str] = None  # should be removed, it is base directory + magellon_session_name name
    task_list: Optional[List] = None  # List to store the tasks List[LeginonFrameTransferTaskDto]


class LeginonFrameTransferTaskDto(BaseModel):
    task_id: uuid.UUID
    task_alias: Optional[str] = None
    file_name: Optional[str] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None
    job_dto: LeginonFrameTransferJobDto
    status: Optional[int] = None


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
    OID: Optional[int] = None
    image_id: Optional[int] = None
    name: Optional[str] = None
    # created_on: Optional[datetime] = None
    data: Optional[str] = None
    OptimisticLockField: Optional[int] = None
    GCRecord: Optional[int] = None
    type: Optional[int] = None
    data_json: Optional[dict] = None


class ParticlePickingDto(BaseModel):
    oid: uuid.UUID
    image_id: uuid.UUID
    name: Optional[str] = None
    data: Optional[str] = None
    data_json: Optional[Json] = None
    status: Optional[int] = None
    type: Optional[int] = None
