# coding: utf-8
import uuid
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


class ImageMetaDataCategory(Base):
    __tablename__ = 'image_meta_data_category'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
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
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    pipeline = relationship('Pipeline')


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
    pixel_size = Column(Float(asdecimal=True))
    level = Column(INTEGER(11))
    atlas_delta_row = Column(Float(asdecimal=True))
    atlas_delta_column = Column(Float(asdecimal=True))
    atlas_dimxy = Column(Float(asdecimal=True))
    metadata_ = Column('metadata', LONGTEXT)
    stage_alpha_tilt = Column(Float(asdecimal=True))
    stage_x = Column(Float(asdecimal=True))
    stage_y = Column(Float(asdecimal=True))
    atlas_id = Column(ForeignKey('atlas.oid'), index=True)
    last_accessed_date = Column(DateTime)
    frame_count = Column(INTEGER(11))
    acceleration_voltage = Column(Float(asdecimal=True))
    spherical_aberration = Column(Float(asdecimal=True))

    atlas = relationship('Atlas')
    parent = relationship('Image', remote_side=[oid])
    session = relationship('Msession')


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

    image = relationship('Image')
    job = relationship('ImageJob')
    pipeline_item = relationship('PipelineItem')


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
