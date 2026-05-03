# coding: utf-8
import re
import uuid
from datetime import datetime
from sqlalchemy_utils import UUIDType
from sqlalchemy.orm import relationship
from lib.sqlalchemy_uuid_type import SqlalchemyUuidType
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGTEXT, SMALLINT, BIT,  LONGBLOB ,DOUBLE
from sqlalchemy import Column, DECIMAL, ForeignKey, Index, String, Text, Boolean, LargeBinary, DateTime, JSON,  BINARY, Float

Base = declarative_base()
metadata = Base.metadata


class Camera(Base):
    __tablename__ = 'camera'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    def validate_name(self) -> bool:
        return bool(self.name and 2 <= len(self.name) <= 30)


class ImageMetaDataCategory(Base):
    __tablename__ = 'image_meta_data_category'

    oid = Column(INTEGER(11), primary_key=True)
    name = Column(String(100))
    parent_id = Column(ForeignKey('image_meta_data_category.oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    parent = relationship('ImageMetaDataCategory', remote_side=[oid])


class Microscope(Base):
    __tablename__ = 'microscope'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class PluginType(Base):
    __tablename__ = 'plugin_type'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(100))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class SampleGridType(Base):
    __tablename__ = 'sample_grid_type'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class SampleType(Base):
    __tablename__ = 'sample_type'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Xpobjecttype(Base):
    __tablename__ = 'xpobjecttype'

    OID = Column(INTEGER(11), primary_key=True)
    TypeName = Column(String(254), unique=True)
    AssemblyName = Column(String(254))


class SysSecRole(Base):
    __tablename__ = 'sys_sec_role'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    Name = Column(String(100))
    IsAdministrative = Column(BIT(1))
    CanEditModel = Column(BIT(1))
    PermissionPolicy = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    ObjectType = Column(ForeignKey('xpobjecttype.OID'), index=True)

    xpobjecttype = relationship('Xpobjecttype')


class SysSecUser(Base):
    __tablename__ = 'sys_sec_user'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    omid = Column(BIGINT(20))
    ouid = Column(String(20))
    created_date = Column(DateTime)
    created_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    last_modified_date = Column(DateTime)
    last_modified_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    deleted_date = Column(DateTime)
    deleted_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    sync_status = Column(INTEGER(11))
    version = Column(String(10))
    PASSWORD = Column(LONGTEXT)
    ChangePasswordOnFirstLogon = Column(BIT(1))
    USERNAME = Column(String(100))
    ACTIVE = Column(BIT(1))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    ObjectType = Column(ForeignKey('xpobjecttype.OID'), index=True)
    AccessFailedCount = Column(INTEGER(11))
    LockoutEnd = Column(DateTime)

    xpobjecttype = relationship('Xpobjecttype')
    parent = relationship('SysSecUser', remote_side=[oid], primaryjoin='SysSecUser.created_by == SysSecUser.oid')
    parent1 = relationship('SysSecUser', remote_side=[oid], primaryjoin='SysSecUser.deleted_by == SysSecUser.oid')
    parent2 = relationship('SysSecUser', remote_side=[oid], primaryjoin='SysSecUser.last_modified_by == SysSecUser.oid')


class Pipeline(Base):
    __tablename__ = 'pipeline'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    omid = Column(BIGINT(20))
    ouid = Column(String(20))
    created_date = Column(DateTime)
    created_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    last_modified_date = Column(DateTime)
    last_modified_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    deleted_date = Column(DateTime)
    deleted_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    sync_status = Column(INTEGER(11))
    version = Column(String(10))
    name = Column(String(100))
    data = Column(LONGTEXT)
    data_json = Column(JSON)
    Description = Column(LONGTEXT)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_user = relationship('SysSecUser', primaryjoin='Pipeline.created_by == SysSecUser.oid')
    sys_sec_user1 = relationship('SysSecUser', primaryjoin='Pipeline.deleted_by == SysSecUser.oid')
    sys_sec_user2 = relationship('SysSecUser', primaryjoin='Pipeline.last_modified_by == SysSecUser.oid')


class Plugin(Base):
    __tablename__ = 'plugin'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    omid = Column(BIGINT(20))
    ouid = Column(String(20))
    created_date = Column(DateTime)
    created_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    last_modified_date = Column(DateTime)
    last_modified_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    deleted_date = Column(DateTime)
    deleted_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    sync_status = Column(INTEGER(11))
    version = Column(String(10))
    name = Column(String(100))
    author = Column(String(100))
    copyright = Column(Text)
    type_id = Column(ForeignKey('plugin_type.oid'), index=True)
    status_id = Column(INTEGER(11))
    coresponding = Column(String(100))
    documentation = Column(LONGTEXT)
    website = Column(String(250))
    input_json = Column(JSON)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_user = relationship('SysSecUser', primaryjoin='Plugin.created_by == SysSecUser.oid')
    sys_sec_user1 = relationship('SysSecUser', primaryjoin='Plugin.deleted_by == SysSecUser.oid')
    sys_sec_user2 = relationship('SysSecUser', primaryjoin='Plugin.last_modified_by == SysSecUser.oid')
    type = relationship('PluginType')


class Project(Base):
    __tablename__ = 'project'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    description = Column(String(200))
    start_on = Column(DateTime)
    end_on = Column(DateTime)
    owner_id = Column(ForeignKey('sys_sec_user.oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    last_accessed_date = Column(DateTime)

    owner = relationship('SysSecUser')


class Site(Base):
    __tablename__ = 'site'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    address = Column(String(150))
    manager_id = Column(ForeignKey('sys_sec_user.oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    manager = relationship('SysSecUser')


class SysSecActionPermission(Base):
    __tablename__ = 'sys_sec_action_permission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    ActionId = Column(String(100))
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecLoginInfo(Base):
    __tablename__ = 'sys_sec_login_info'
    __table_args__ = (
        Index('iLoginProviderNameProviderUserKey_sys_sec_login_info', 'LoginProviderName', 'ProviderUserKey', unique=True),
    )

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    LoginProviderName = Column(String(100))
    ProviderUserKey = Column(String(100))
    User = Column(ForeignKey('sys_sec_user.oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))

    sys_sec_user = relationship('SysSecUser')


class SysSecNavigationPermission(Base):
    __tablename__ = 'sys_sec_navigation_permission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    ItemPath = Column(LONGTEXT)
    NavigateState = Column(INTEGER(11))
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecTypePermission(Base):
    __tablename__ = 'sys_sec_type_permission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    TargetType = Column(LONGTEXT)
    ReadState = Column(INTEGER(11))
    WriteState = Column(INTEGER(11))
    CreateState = Column(INTEGER(11))
    DeleteState = Column(INTEGER(11))
    NavigateState = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecUserRole(Base):
    __tablename__ = 'sys_sec_user_role'
    __table_args__ = (
        Index('iRolesPeople_sys_sec_user_role', 'Roles', 'People', unique=True),
    )

    Roles = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    People = Column(ForeignKey('sys_sec_user.oid'), index=True)
    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    OptimisticLockField = Column(INTEGER(11))

    sys_sec_user = relationship('SysSecUser')
    sys_sec_role = relationship('SysSecRole')


class ImageJob(Base):
    __tablename__ = 'image_job'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(100))
    description = Column(Text)
    created_date = Column(DateTime)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    user_id = Column(String(100))
    project_id = Column(String(100))
    msession_id = Column(String(100))
    status_id = Column(SMALLINT(5))
    type_id = Column(SMALLINT(5))
    data = Column(LONGTEXT)
    data_json = Column(JSON)
    processed_json = Column(JSON)
    output_directory = Column(String(250))
    direction = Column(SMALLINT(5))
    image_selection_criteria = Column(Text)
    pipeline_id = Column(ForeignKey('pipeline.oid'), index=True)
    plugin_id = Column(String(100), index=True)
    settings = Column(JSON)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    # Phase 8 (migration 0006): a job may belong to a PipelineRun
    # rollup. Nullable so pre-Phase-8 jobs remain valid as
    # standalone runs.
    parent_run_id = Column(ForeignKey('pipeline_run.oid'), index=True, nullable=True)

    pipeline = relationship('Pipeline')
    parent_run = relationship('PipelineRun', back_populates='jobs')


class Msession(Base):
    __tablename__ = 'msession'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(50))
    project_id = Column(ForeignKey('project.oid'), index=True)
    site_id = Column(ForeignKey('site.oid'), index=True)
    user_id = Column(ForeignKey('sys_sec_user.oid'), index=True)
    description = Column(String(250))
    start_on = Column(DateTime)
    end_on = Column(DateTime)
    microscope_id = Column(ForeignKey('microscope.oid'), index=True)
    camera_id = Column(ForeignKey('camera.oid'), index=True)
    sample_type = Column(ForeignKey('sample_type.oid'), index=True)
    sample_name = Column(String(50))
    sample_grid_type = Column(ForeignKey('sample_grid_type.oid'), index=True)
    sample_sequence = Column(Text)
    sample_procedure = Column(LONGTEXT)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    last_accessed_date = Column(DateTime)

    camera = relationship('Camera')
    microscope = relationship('Microscope')
    project = relationship('Project')
    sample_grid_type1 = relationship('SampleGridType')
    sample_type1 = relationship('SampleType')
    site = relationship('Site')
    user = relationship('SysSecUser')


class PipelineItem(Base):
    __tablename__ = 'pipeline_item'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    omid = Column(BIGINT(20))
    ouid = Column(String(20))
    created_date = Column(DateTime)
    created_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    last_modified_date = Column(DateTime)
    last_modified_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    deleted_date = Column(DateTime)
    deleted_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    sync_status = Column(INTEGER(11))
    version = Column(String(10))
    name = Column(String(100))
    pipeline_id = Column(ForeignKey('pipeline.oid'), index=True)
    plugin_id = Column(String(100))
    status = Column(String(100))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_user = relationship('SysSecUser', primaryjoin='PipelineItem.created_by == SysSecUser.oid')
    sys_sec_user1 = relationship('SysSecUser', primaryjoin='PipelineItem.deleted_by == SysSecUser.oid')
    sys_sec_user2 = relationship('SysSecUser', primaryjoin='PipelineItem.last_modified_by == SysSecUser.oid')
    pipeline = relationship('Pipeline')


class SysSecMemberPermission(Base):
    __tablename__ = 'sys_sec_member_permission'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    Members = Column(LONGTEXT)
    ReadState = Column(INTEGER(11))
    WriteState = Column(INTEGER(11))
    Criteria = Column(LONGTEXT)
    TypePermissionObject = Column(ForeignKey('sys_sec_type_permission.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_type_permission = relationship('SysSecTypePermission')


class SysSecObjectPermission(Base):
    __tablename__ = 'sys_sec_object_permission'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    Criteria = Column(LONGTEXT)
    ReadState = Column(INTEGER(11))
    WriteState = Column(INTEGER(11))
    DeleteState = Column(INTEGER(11))
    NavigateState = Column(INTEGER(11))
    TypePermissionObject = Column(ForeignKey('sys_sec_type_permission.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_type_permission = relationship('SysSecTypePermission')


class Atlas(Base):
    __tablename__ = 'atlas'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(100))
    meta = Column(LONGTEXT)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    session_id = Column(ForeignKey('msession.oid'), index=True)

    session = relationship('Msession')


class SampleMaterial(Base):
    __tablename__ = 'sample_material'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    session = Column(ForeignKey('msession.oid'), index=True)
    name = Column(String(30))
    quantity = Column(DECIMAL(28, 8))
    note = Column(String(150))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    msession = relationship('Msession')


class Image(Base):
    __tablename__ = 'image'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(100))
    frame_name = Column(String(100))
    frame_count = Column(INTEGER(11))
    path = Column(String(300))
    parent_id = Column(ForeignKey('image.oid', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    session_id = Column(ForeignKey('msession.oid', ondelete='CASCADE', onupdate='CASCADE'), index=True)
    magnification = Column(BIGINT(20))
    dose = Column(DECIMAL(28, 8))
    focus = Column(DECIMAL(28, 8))
    defocus = Column(DECIMAL(28, 8))
    spot_size = Column(BIGINT(20))
    intensity = Column(DECIMAL(28, 8))
    shift_x = Column(DECIMAL(28, 8))
    shift_y = Column(DECIMAL(28, 8))
    beam_shift_x = Column(DECIMAL(28, 8))
    beam_shift_y = Column(DECIMAL(28, 8))
    reset_focus = Column(BIGINT(20))
    screen_current = Column(BIGINT(20))
    beam_bank = Column(String(150))
    condenser_x = Column(DECIMAL(28, 8))
    condenser_y = Column(DECIMAL(28, 8))
    objective_x = Column(DECIMAL(28, 8))
    objective_y = Column(DECIMAL(28, 8))
    dimension_x = Column(BIGINT(20))
    dimension_y = Column(BIGINT(20))
    binning_x = Column(BIGINT(20))
    binning_y = Column(BIGINT(20))
    offset_x = Column(BIGINT(20))
    offset_y = Column(BIGINT(20))
    exposure_time = Column(DECIMAL(28, 8))
    exposure_type = Column(BIGINT(20))
    pixel_size_x = Column(DECIMAL(28, 8))
    pixel_size_y = Column(DECIMAL(28, 8))
    energy_filtered = Column(BIT(1))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    previous_id = Column(BIGINT(20))
    pixel_size = Column(DECIMAL(asdecimal=True))
    level = Column(INTEGER(11))
    atlas_delta_row = Column(DECIMAL(asdecimal=True))
    atlas_delta_column = Column(DECIMAL(asdecimal=True))
    atlas_dimxy = Column(DECIMAL(asdecimal=True))
    metadata_ = Column('metadata', LONGTEXT)
    stage_alpha_tilt = Column(DECIMAL(asdecimal=True))
    stage_x = Column(DECIMAL(asdecimal=True))
    stage_y = Column(DECIMAL(asdecimal=True))
    atlas_id = Column(ForeignKey('atlas.oid'), index=True)
    last_accessed_date = Column(DateTime)
    acceleration_voltage = Column(DECIMAL(asdecimal=True))
    spherical_aberration = Column(DECIMAL(asdecimal=True))

    atlas = relationship('Atlas')
    parent = relationship('Image', remote_side=[oid])
    session = relationship('Msession')

    def derive_parent_name(self) -> str:
        """Derive the expected parent image name from this image's name.
        E.g., '23oct13x_a_00034gr_00008sq_v02' -> '23oct13x_a_00034gr_00008sq'
        """
        split_name = self.name.split('_')
        if re.search(r'[vV]([0-9][0-9])', split_name[-1]):
            return '_'.join(split_name[:-2])
        return '_'.join(split_name[:-1])

    def compute_level(self, presets_pattern: str) -> int:
        """Compute the image level based on how many preset patterns match the name."""
        if not presets_pattern:
            return 0
        return len(re.findall(presets_pattern, self.name))

    @property
    def is_exposure(self) -> bool:
        """Check if this is an exposure-level image (contains 'ex' in name)."""
        return bool(re.search(r'_\d+ex', self.name)) if self.name else False

    @property
    def session_name_from_filename(self) -> str:
        """Extract session name from the image filename (text before first underscore)."""
        if not self.name:
            return ""
        idx = self.name.find('_')
        return self.name[:idx].lower() if idx > 0 else self.name.lower()


class ImageJobTask(Base):
    __tablename__ = 'image_job_task'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    job_id = Column(ForeignKey('image_job.oid'), index=True)
    image_id = Column(ForeignKey('image.oid'), index=True)
    status_id = Column(SMALLINT(5))
    type_id = Column(SMALLINT(5))
    data = Column(LONGTEXT)
    data_json = Column(JSON)
    processed_json = Column(JSON)
    pipeline_item_id = Column(ForeignKey('pipeline_item.oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    stage = Column(INTEGER(11))
    image_name = Column(String(255))
    image_path = Column(String(255))
    frame_name = Column(String(255))
    frame_path = Column(String(255))
    # Per-task provenance (P4 / migration 0003). Records which plugin
    # (and which version of it) produced this task's result.
    plugin_id = Column(String(100), index=True)
    plugin_version = Column(String(50))

    # Subject axis (Phase 3 / migration 0004). Pre-Phase-3 every task
    # was image-keyed via ``image_id``. The CAN classifier doesn't fit
    # — its subject is a ``particle_stack``, not an image — so we
    # generalise. ``subject_kind`` is VARCHAR per ratified rule 4
    # (project_artifact_bus_invariants.md, 2026-05-03): MySQL ENUM
    # ALTER on a tens-of-millions-row table is multi-hour; VARCHAR is
    # a code-only change to add a new kind. The migration backfills
    # subject_id = image_id for every existing row, so image-keyed
    # plugins keep working unchanged.
    subject_kind = Column(String(32), nullable=False, server_default='image')
    subject_id = Column(SqlalchemyUuidType, nullable=True)

    image = relationship('Image')
    job = relationship('ImageJob')
    pipeline_item = relationship('PipelineItem')


class PipelineRun(Base):
    """User-visible rollup over a sequence of ImageJobs.

    Phase 8 (migration 0006). Each algorithm step (motioncor, ctf,
    picker, extraction, classification) is its own ImageJob;
    PipelineRun groups them so the UI can show "I ran the picker →
    extractor → classifier on session X" as a single thing.

    Status enum mirrors ImageJob.status_id: 1=pending, 2=running,
    3=processing, 4=completed, 5=failed, 6=cancelled. ``settings``
    is free-form workflow parameters (cryoSPARC's analogue is
    Workflow inputs). ``deleted_at`` is the only mutable field on a
    completed run — soft-delete only, mirrors the artifact pattern.
    """

    __tablename__ = 'pipeline_run'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(200))
    description = Column(Text)
    msession_id = Column(String(100), index=True)
    status_id = Column(SMALLINT(5), nullable=False, server_default="1")
    created_date = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    started_date = Column(DateTime)
    ended_date = Column(DateTime)
    settings = Column(JSON)
    user_id = Column(String(100))
    deleted_at = Column(DateTime)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    jobs = relationship(
        'ImageJob',
        back_populates='parent_run',
        order_by='ImageJob.created_date',
    )


class Artifact(Base):
    """Typed bridge between a producing job/task and its consumers.

    Phase 4 (migration 0005). Single-table inheritance: queryable hot
    fields promoted to columns (``kind``, ``producing_*``,
    ``mrcs_path``, ``star_path``, ``particle_count``, ``apix``,
    ``box_size``); long-tail per-kind metadata in ``data_json``.

    Per ratified rule 6 (project_artifact_bus_invariants.md): artifacts
    are immutable once written. A re-run produces a *new* row pointing
    at the same source. ``deleted_at`` is the only mutable field on a
    written artifact.
    """

    __tablename__ = 'artifact'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    kind = Column(String(32), nullable=False, index=True)

    producing_job_id = Column(ForeignKey('image_job.oid'), index=True)
    producing_task_id = Column(ForeignKey('image_job_task.oid'), index=True)
    msession_id = Column(String(100))

    # Lineage (alembic 0007, reviewer-flagged High #5). Self-FK to
    # the artifact this one was derived from. Nullable for
    # top-of-pipeline outputs (extraction). ON DELETE SET NULL keeps
    # soft-delete on the source clean.
    source_artifact_id = Column(
        ForeignKey('artifact.oid', ondelete='SET NULL'),
        index=True,
        nullable=True,
    )

    # Promoted hot columns — queryable scalars / paths.
    mrcs_path = Column(String(500))
    star_path = Column(String(500))
    particle_count = Column(INTEGER(11))
    apix = Column(DECIMAL(asdecimal=False))
    box_size = Column(INTEGER(11))

    # Long-tail per-kind metadata.
    data_json = Column(JSON)

    created_date = Column(DateTime, nullable=False, default=lambda: datetime.utcnow())
    deleted_at = Column(DateTime, nullable=True)

    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    producing_job = relationship('ImageJob')
    producing_task = relationship('ImageJobTask')
    source_artifact = relationship(
        'Artifact', remote_side=[oid], foreign_keys=[source_artifact_id],
    )


class ImageMetaData(Base):
    __tablename__ = 'image_meta_data'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    omid = Column(BIGINT(20))
    ouid = Column(String(20))
    created_date = Column(DateTime)
    created_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    last_modified_date = Column(DateTime)
    last_modified_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    deleted_date = Column(DateTime)
    deleted_by = Column(ForeignKey('sys_sec_user.oid'), index=True)
    sync_status = Column(INTEGER(11))
    version = Column(String(10))
    image_id = Column(ForeignKey('image.oid'), index=True)
    name = Column(String(100))
    alias = Column(String(100))
    job_id = Column(ForeignKey('image_job.oid'), index=True)
    task_id = Column(ForeignKey('image_job_task.oid'), index=True)
    category_id = Column(ForeignKey('image_meta_data_category.oid'), index=True)
    data = Column(LONGTEXT)
    data_json = Column(JSON)
    processed_json = Column(JSON)
    plugin_id = Column(ForeignKey('plugin.oid'), index=True)
    status_id = Column(INTEGER(11))
    plugin_type_id = Column(ForeignKey('plugin_type.oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    type = Column(INTEGER(11))

    category = relationship('ImageMetaDataCategory')
    sys_sec_user = relationship('SysSecUser', primaryjoin='ImageMetaData.created_by == SysSecUser.oid')
    sys_sec_user1 = relationship('SysSecUser', primaryjoin='ImageMetaData.deleted_by == SysSecUser.oid')
    image = relationship('Image')
    job = relationship('ImageJob')
    sys_sec_user2 = relationship('SysSecUser', primaryjoin='ImageMetaData.last_modified_by == SysSecUser.oid')
    plugin = relationship('Plugin')
    plugin_type = relationship('PluginType')
    task = relationship('ImageJobTask')


class JobEvent(Base):
    """Append-only log of lifecycle events (step started / completed /
    failed) received from plugins via NATS and/or RMQ.

    Named ``job_event`` — not ``image_job_event`` — so future non-image
    jobs can share the log without a rename. Rows are keyed by
    ``event_id`` (CloudEvents ``id``) with a UNIQUE constraint, giving
    idempotent writes: the same logical event arriving on both
    channels produces exactly one row.

    Progress events are *not* persisted — they're live-only
    notifications. Only lifecycle transitions land here.
    """
    __tablename__ = 'job_event'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    job_id = Column(ForeignKey('image_job.oid'), index=True, nullable=False)
    task_id = Column(ForeignKey('image_job_task.oid'), index=True)
    event_type = Column(String(64), nullable=False, index=True)
    step = Column(String(64), nullable=False, index=True)
    source = Column(String(200))
    ts = Column(DateTime, nullable=False)
    data_json = Column(JSON)
    created_date = Column(DateTime, nullable=False)

    job = relationship('ImageJob')
    task = relationship('ImageJobTask')
