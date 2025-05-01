from enum import Enum
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import uuid

class EventType(str, Enum):
    """
    Standard event types for the JobManager system.
    Follow a hierarchical pattern: object.action
    """
    # ======== Job Lifecycle Events ========
    JOB_CREATED = "org.magellon.job.created"
    JOB_UPDATED = "org.magellon.job.updated"
    JOB_COMPLETED = "org.magellon.job.completed"
    JOB_FAILED = "org.magellon.job.failed"
    JOB_CANCELLED = "org.magellon.job.cancelled"
    JOB_STARTED = "org.magellon.job.started"
    JOB_PROGRESS = "org.magellon.job.progress"
    JOB_CANCELLATION_REQUESTED = "job.cancellation.requested"

    # ======== Task Lifecycle Events ========
    TASK_CREATED = "org.magellon.task.created"
    TASK_STARTED = "org.magellon.task.started"
    TASK_PROGRESS = "org.magellon.task.progress"
    TASK_COMPLETED = "org.magellon.task.completed"
    TASK_FAILED = "org.magellon.task.failed"
    TASK_CANCELLED = "org.magellon.task.cancelled"
    TASK_CANCELLATION_REQUESTED = "org.magellon.task.cancellation.requested"

    # ======== Import Process Events ========
    # Database operations
    DB_PROJECT_CREATED = "db.project.created"
    DB_PROJECT_UPDATED = "db.project.updated"
    DB_SESSION_CREATED = "db.session.created"
    DB_SESSION_UPDATED = "db.session.updated"
    DB_IMAGE_CREATED = "db.image.created"
    DB_IMAGE_BATCH_CREATED = "db.image.batch.created"
    DB_ATLAS_CREATED = "db.atlas.created"

    # Directory operations
    DIR_CREATED = "directory.created"
    DIR_STRUCTURE_CREATED = "directory.structure.created"

    # File operations
    FILE_COPIED = "file.copied"
    FILE_TRANSFERRED = "file.transferred"
    FRAME_TRANSFERRED = "file.frame.transferred"
    IMAGE_COPIED = "file.image.copied"

    # Processing operations
    IMAGE_CONVERTED = "processing.image.converted"
    FFT_COMPUTED = "processing.fft.computed"
    CTF_COMPUTED = "processing.ctf.computed"
    MOTIONCOR_COMPUTED = "processing.motioncor.computed"
    ATLAS_GENERATED = "processing.atlas.generated"

    # ======== Importer-specific Events ========
    # EPU Importer
    EPU_METADATA_LOADED = "import.epu.metadata.loaded"
    EPU_DIRECTORY_SCANNED = "import.epu.directory.scanned"
    EPU_XML_PARSED = "import.epu.xml.parsed"

    # Leginon Importer
    LEGINON_SESSION_LOADED = "import.leginon.session.loaded"
    LEGINON_DB_CONNECTED = "import.leginon.db.connected"
    LEGINON_IMAGES_LOADED = "import.leginon.images.loaded"

    # SerialEM Importer
    SERIALEM_DIRECTORY_SCANNED = "import.serialem.directory.scanned"
    SERIALEM_MDOC_PARSED = "import.serialem.mdoc.parsed"

    # Magellon Importer
    MAGELLON_SESSION_LOADED = "import.magellon.session.loaded"
    MAGELLON_IMAGES_LOADED = "import.magellon.images.loaded"

    # ======== System Events ========
    SYSTEM_ERROR = "system.error"
    SYSTEM_WARNING = "system.warning"
    SYSTEM_INFO = "system.info"