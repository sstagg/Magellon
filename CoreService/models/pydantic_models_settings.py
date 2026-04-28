import os
import uuid
from enum import Enum
from typing import List, Optional

import yaml
from pydantic import BaseModel, ValidationError


class OutQueueType(str, Enum):
    """Categories of result queues the in-process result-processor consumes.

    Mirrors the plugin's old enum (now folded into CoreService — see P3).
    The string values double as default ``dir_name`` lookups when a queue
    config doesn't override.
    """

    CTF = "ctf"
    MOTIONCOR = "motioncor"
    FFT = "fft"
    PARTICLE_PICKING = "particle_picking"
    SQUARE_DETECTION = "square_detection"
    HOLE_DETECTION = "hole_detection"
    TOPAZ_PICK = "topaz_pick"
    MICROGRAPH_DENOISE = "micrograph_denoise"


class OutQueueConfig(BaseModel):
    """One result-queue subscription for the in-process result-processor.

    ``name`` is the RMQ queue. ``queue_type`` selects the per-category
    metadata. ``dir_name`` overrides the on-disk subfolder used when
    moving output files (defaults to ``queue_type``). ``category``
    is the ``image_meta_data.category_id`` to stamp on saved metadata.
    """

    name: str
    queue_type: OutQueueType
    dir_name: Optional[str] = None
    category: Optional[int] = None


class RabbitMQSettings(BaseModel):
    HOST_NAME: Optional[str] = None
    CTF_QUEUE_NAME: Optional[str] = None
    CTF_OUT_QUEUE_NAME: Optional[str] = None
    MOTIONCOR_QUEUE_NAME: Optional[str] = None
    MOTIONCOR_OUT_QUEUE_NAME: Optional[str] = None
    MOTIONCOR_TEST_QUEUE_NAME: Optional[str] = None
    MOTIONCOR_TEST_OUT_QUEUE_NAME: Optional[str] = None
    FFT_QUEUE_NAME: Optional[str] = "fft_tasks_queue"
    FFT_OUT_QUEUE_NAME: Optional[str] = "fft_out_tasks_queue"
    SQUARE_DETECTION_QUEUE_NAME: Optional[str] = "square_detection_tasks_queue"
    SQUARE_DETECTION_OUT_QUEUE_NAME: Optional[str] = "square_detection_out_tasks_queue"
    HOLE_DETECTION_QUEUE_NAME: Optional[str] = "hole_detection_tasks_queue"
    HOLE_DETECTION_OUT_QUEUE_NAME: Optional[str] = "hole_detection_out_tasks_queue"
    TOPAZ_PICK_QUEUE_NAME: Optional[str] = "topaz_pick_tasks_queue"
    TOPAZ_PICK_OUT_QUEUE_NAME: Optional[str] = "topaz_pick_out_tasks_queue"
    MICROGRAPH_DENOISE_QUEUE_NAME: Optional[str] = "micrograph_denoise_tasks_queue"
    MICROGRAPH_DENOISE_OUT_QUEUE_NAME: Optional[str] = "micrograph_denoise_out_tasks_queue"
    PORT: Optional[int] = 5672
    USER_NAME: Optional[str] = None
    PASSWORD: Optional[str] = None
    VIRTUAL_HOST: Optional[str] = None
    SSL_ENABLED: Optional[bool] = False
    CONNECTION_TIMEOUT: Optional[int] = 30
    PREFETCH_COUNT: Optional[int] = 10
    # Result-processor fan-in. The in-process consumer (see
    # ``core.result_consumer``) subscribes to every entry here. Empty
    # list = result-processor stays dormant, which is the safe default
    # for any deployment that hasn't migrated off the out-of-tree plugin.
    OUT_QUEUES: List[OutQueueConfig] = []


class DirectorySettings(BaseModel):
    IMAGE_ROOT_URL: Optional[str] = None
    ORIGINAL_IMAGES_SUB_URL: Optional[str] = None
    IMAGE_SUB_URL: Optional[str] = None
    THUMBNAILS_SUB_URL: Optional[str] = None
    FRAMES_SUB_URL: Optional[str] = None
    JOBS_PROCESSING_SUB_URL: Optional[str] = None
    THUMBNAILS_SUFFIX: Optional[str] = None
    FRAMES_SUFFIX: Optional[str] = None
    FFT_SUB_URL: Optional[str] = None
    FFT_SUFFIX: Optional[str] = None
    FFT_DIR: Optional[str] = None
    MAGELLON_HOME_DIR: Optional[str] = None
    MAGELLON_GPFS_PATH: Optional[str] = None
    NFS_ROOT_DIR: Optional[str] = None
    IMAGES_DIR: Optional[str] = None
    THUMBNAILS_DIR: Optional[str] = None
    MAGELLON_JOBS_DIR: Optional[str] = None
    JOBS_DIR: Optional[str] = None
    ATLAS_SUB_URL: Optional[str] = None
    CTF_SUB_URL: Optional[str] = None
    FAO_SUB_URL: Optional[str] = None
    GAIN_SUB_URL: Optional[str] = None
    DEFECTS_SUB_URL: Optional[str] = None
    ATLAS_SUFFIX: Optional[str] = None


class DatabaseSettings(BaseModel):
    DB_Driver: Optional[str] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_Port: Optional[int] = None
    DB_NAME: Optional[str] = None

    @classmethod
    def get_db_connection(cls) -> str:
        """
        Get the database connection string.
        """
        return f'{cls.DB_Driver}://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_Port}/{cls.DB_NAME}'


class LeginonDatabaseSettings(BaseModel):
    """
    Settings for external Leginon database connection.
    Used for importing Leginon session data and creating atlases.
    """
    ENABLED: Optional[bool] = False
    HOST: Optional[str] = None
    PORT: Optional[int] = 3310
    USER: Optional[str] = None
    PASSWORD: Optional[str] = None
    DATABASE: Optional[str] = "dbemdata"


class ApiDocsSettings(BaseModel):
    """
    Settings for API documentation HTTP Basic Authentication.
    Protects /docs and /openapi.json endpoints.
    """
    ENABLED: Optional[bool] = True
    USERNAME: Optional[str] = "admin"
    PASSWORD: Optional[str] = "changeme"


class SecuritySetupSettings(BaseModel):
    """
    Settings for security system bootstrap/setup endpoint.
    Used during initial application installation to create admin user.
    """
    ENABLED: Optional[bool] = True
    SETUP_TOKEN: Optional[str] = None  # Optional token for extra security
    AUTO_DISABLE: Optional[bool] = True  # Automatically disable after first successful run


class AppSettings(BaseModel):
    directory_settings: DirectorySettings = DirectorySettings()
    database_settings: DatabaseSettings = DatabaseSettings()
    rabbitmq_settings: RabbitMQSettings = RabbitMQSettings()
    leginon_db_settings: LeginonDatabaseSettings = LeginonDatabaseSettings()
    api_docs_settings: ApiDocsSettings = ApiDocsSettings()
    security_setup_settings: SecuritySetupSettings = SecuritySetupSettings()
    SLACK_TOKEN: Optional[str] = None
    BASE_DIRECTORY: Optional[str] = os.path.abspath(os.path.dirname(__file__))
    DOCKER_URL: Optional[str] = None
    DOCKER_REPOSITORY: Optional[str] = None
    DOCKER_USERNAME: Optional[str] = None
    DOCKER_PASSWORD: Optional[str] = None

    DEBUG_CTF: Optional[bool] = None
    DEBUG_CTF_PATH: Optional[str] = None
    DEBUG_CTF_REPLACE: Optional[str] = None

    # Auto-dispatch topaz tasks during the import pipeline. Off by default —
    # topaz applies only to high-mag exposures (pixel size <= 5 A/px) and
    # producing picks for every exposure may not be desired in every session.
    # Operators can flip these on per-environment via YAML to enable
    # automatic per-image picking / denoising alongside CTF + MotionCor.
    AUTO_DISPATCH_TOPAZ_PICK: Optional[bool] = False
    AUTO_DISPATCH_TOPAZ_DENOISE: Optional[bool] = False

    ENV_TYPE: Optional[str] = None

    @classmethod
    def load_settings(cls, file_path):
        """
        Load settings from a JSON file and update the AppSettings instance.
        """
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                data_dict = yaml.safe_load(file)
            try:
                obj = cls.parse_obj(data_dict)
                return obj
            except ValidationError as e:
                print(f"Validation error: {e}")
                # Handle validation error if necessary
                return None
        else:
            # Handle case when file doesn't exist
            return None

    @classmethod
    def load_settings_json(cls, file_path):
        """
        Load settings from a JSON file and update the AppSettings instance.
        """
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                settings_json = file.read()
            try:
                json = cls.model_validate_json(settings_json)
                return json
            except ValidationError:
                # Handle validation error if necessary
                return None
        else:
            # Handle case when file doesn't exist
            return None

    def save_settings(self, file_path: str):
        with open(file_path, "w") as file:
            yaml.dump(self.dict(), file)

    def save_settings_json(self, file_path: str):
        """
        Save the AppSettings instance to a JSON file.
        """
        with open(file_path, 'w') as file:
            file.write(self.model_dump_json())
