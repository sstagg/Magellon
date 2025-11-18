from enum import Enum
from fastapi import UploadFile, File
from pydantic import BaseModel, Field, Json, ValidationInfo, field_validator, ConfigDict
from typing import Any,Optional, List
import uuid
from uuid import UUID
from datetime import datetime

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
    # job_id: Optional[uuid.UUID] = None
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


class MagellonImportJobDto(BaseModel):
    source_dir: str


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
    binning_x:Optional[int]=1


class LeginonFrameTransferJobBase(ImportJobBase):
    leginon_mysql_host: Optional[str] = None
    leginon_mysql_port: Optional[int]
    leginon_mysql_db: Optional[str] = None
    leginon_mysql_user: Optional[str] = None
    leginon_mysql_pass: Optional[str] = None
    defects_file: Optional[UploadFile] = File(None)

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

class EpuImportJobBase(ImportJobBase):

    epu_dir_path: Optional[str] = None

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
class DefaultParams(BaseModel):
    pixel_size : float = 0.739
    acceleration_voltage: float = 300
    spherical_aberration: float =2.7
    magnification: int = 5000
    dose: float = 1.0
    defocus: float = 15000
    amplitude_contrast: float = 0.07
    detector_pixel_size: int = 5

class EpuImportJobDto(EpuImportJobBase):
    target_directory: Optional[str] = None  # should be removed, it is base directory + magellon_session_name name
    default_data: Optional[DefaultParams] = None

class EPUImportTaskDto(ImportTaskDto):
    job_dto: EpuImportJobDto



class SerialEMImportJobBase(ImportJobBase):
    serial_em_dir_path: Optional[str] = None
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

class SerialEMImportJobDto(SerialEMImportJobBase):
    target_directory: Optional[str] = None  # should be removed, it is base directory + magellon_session_name name
    default_data: Optional[DefaultParams] = None
class SerialEMImportTaskDto(ImportTaskDto):
    job_dto: SerialEMImportJobDto





class LeginonFrameTransferJobDto(LeginonFrameTransferJobBase):
    target_directory: Optional[str] = None  # should be removed, it is base directory + magellon_session_name name
    defects_file: Optional[UploadFile] = None   
    gains_file: Optional[UploadFile] = None




class ImportTaskDto(BaseModel):
    task_id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    task_alias: Optional[str] = None
    file_name: Optional[str] = None
    image_id: Optional[uuid.UUID] = None
    image_name: Optional[str] = None
    image_path: Optional[str] = None
    frame_name: Optional[str] = None
    frame_path: Optional[str] = None
    status: Optional[int] = None
    pixel_size: Optional[float] = None
    acceleration_voltage: Optional[float] = None
    spherical_aberration: Optional[float] = None
    amplitude_contrast: Optional[float] = 0.07
    size_of_amplitude_spectrum: Optional[int] = 512
    minimum_resolution: Optional[int] = 30
    maximum_resolution: Optional[int] = 5
    minimum_defocus: Optional[int] = 5000
    maximum_defocus: Optional[int] = 50000
    defocus_search_step: Optional[int] = 100
    binning_x: Optional[int]=1

class LeginonFrameTransferTaskDto(ImportTaskDto):
    job_dto: LeginonFrameTransferJobDto



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



class SysSecUserDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    oid: Optional[UUID] = None
    omid: Optional[int] = None
    ouid: Optional[str] = Field(None, max_length=20)
    created_date: Optional[datetime] = None
    created_by: Optional[UUID] = None
    last_modified_date: Optional[datetime] = None
    last_modified_by: Optional[UUID] = None
    deleted_date: Optional[datetime] = None
    deleted_by: Optional[UUID] = None
    sync_status: Optional[int] = None
    version: Optional[str] = Field(None, max_length=10)
    password: Optional[str] = Field(None, alias="PASSWORD")
    change_password_on_first_logon: Optional[bool] = Field(None, alias="ChangePasswordOnFirstLogon")
    username: Optional[str] = Field(None, max_length=100, alias="USERNAME")
    active: Optional[bool] = Field(None, alias="ACTIVE")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")
    object_type: Optional[int] = Field(None, alias="ObjectType")
    access_failed_count: Optional[int] = Field(None, alias="AccessFailedCount")
    lockout_end: Optional[datetime] = Field(None, alias="LockoutEnd")


class SysSecUserCreateDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6)
    active: Optional[bool] = True
    change_password_on_first_logon: Optional[bool] = False
    omid: Optional[int] = None
    ouid: Optional[str] = Field(None, max_length=20)
    sync_status: Optional[int] = None
    version: Optional[str] = Field(None, max_length=10)
    object_type: Optional[int] = None


class SysSecUserUpdateDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    oid: UUID
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=6)
    active: Optional[bool] = None
    change_password_on_first_logon: Optional[bool] = None
    omid: Optional[int] = None
    ouid: Optional[str] = Field(None, max_length=20)
    sync_status: Optional[int] = None
    version: Optional[str] = Field(None, max_length=10)
    object_type: Optional[int] = None
    access_failed_count: Optional[int] = None
    lockout_end: Optional[datetime] = None


class SysSecUserResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    oid: UUID
    username: Optional[str] = Field(None, alias="USERNAME")
    active: Optional[bool] = Field(None, alias="ACTIVE")
    created_date: Optional[datetime] = None
    last_modified_date: Optional[datetime] = None
    omid: Optional[int] = None
    ouid: Optional[str] = None
    sync_status: Optional[int] = None
    version: Optional[str] = None
    change_password_on_first_logon: Optional[bool] = Field(None, alias="ChangePasswordOnFirstLogon")
    object_type: Optional[int] = Field(None, alias="ObjectType")
    access_failed_count: Optional[int] = Field(None, alias="AccessFailedCount")
    lockout_end: Optional[datetime] = Field(None, alias="LockoutEnd")


class PasswordHashRequest(BaseModel):
    """
    Request model for generating password hash for manual database recovery.
    This is used when system administrator loses password and needs to manually
    update the sys_sec_user.PASSWORD field.
    """
    password: str = Field(..., min_length=6, description="Plain text password to hash")


class SecuritySetupRequest(BaseModel):
    """
    Request model for bootstrapping security system during application installation.
    Creates admin user, Administrator role, and assigns full permissions.
    """
    username: str = Field(..., min_length=3, max_length=100, description="Admin username")
    password: str = Field(..., min_length=6, description="Admin password")
    setup_token: Optional[str] = Field(None, description="Optional setup token for security")