# coding: utf-8
import uuid

from sqlalchemy import Column, DECIMAL, ForeignKey, Index, String, Text, Boolean, LargeBinary, DateTime, JSON, DOUBLE
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, LONGTEXT, SMALLINT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy_utils import UUIDType

from lib.sqlalchemy_uuid_type import SqlalchemyUuidType

Base = declarative_base()
# Base.query =db_session.query_property
metadata = Base.metadata


class Atlas(Base):
    __tablename__ = 'atlas'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(100))
    meta = Column(LONGTEXT)
    session_id = Column(ForeignKey('msession.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Camera(Base):
    __tablename__ = 'camera'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    # Oid = Column(UUIDType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    # Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Microscope(Base):
    __tablename__ = 'microscope'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Modeldifference(Base):
    __tablename__ = 'modeldifference'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    UserId = Column(String(100))
    ContextId = Column(String(100))
    Version = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Samplegridtype(Base):
    __tablename__ = 'samplegridtype'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Sampletype(Base):
    __tablename__ = 'sampletype'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Xpobjecttype(Base):
    __tablename__ = 'xpobjecttype'

    OID = Column(INTEGER(11), primary_key=True)
    TypeName = Column(String(254), unique=True)
    AssemblyName = Column(String(254))


class Modeldifferenceaspect(Base):
    __tablename__ = 'modeldifferenceaspect'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Name = Column(String(100))
    Xml = Column(Text)
    Owner = Column(ForeignKey('modeldifference.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    modeldifference = relationship('Modeldifference')


class SysSecParty(Base):
    __tablename__ = 'sys_sec_party'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    omid = Column(BIGINT(20))
    ouid = Column(String(20))
    createdOn = Column(DateTime)
    createdBy = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    lastModifiedOn = Column(DateTime)
    lastModifiedBy = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    syncStatus = Column(INTEGER(11))
    version = Column(BIGINT(20))
    Color = Column(INTEGER(11))
    fullName = Column(String(100))
    mobile = Column(String(15))
    phone = Column(String(15))
    email = Column(String(100))
    address = Column(String(100))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    ObjectType = Column(ForeignKey('xpobjecttype.OID'), index=True)
    Password = Column(Text)
    ChangePasswordOnFirstLogon = Column(Boolean, default=True)
    UserName = Column(String(100))
    IsActive = Column(Boolean, default=True)
    photo = Column(LargeBinary)

    xpobjecttype = relationship('Xpobjecttype')
    parent = relationship('SysSecParty', remote_side=[Oid], primaryjoin='SysSecParty.createdBy == SysSecParty.Oid')
    parent1 = relationship('SysSecParty', remote_side=[Oid],
                           primaryjoin='SysSecParty.lastModifiedBy == SysSecParty.Oid')


class SysSecRole(Base):
    __tablename__ = 'sys_sec_role'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Name = Column(String(100))
    IsAdministrative = Column(Boolean, default=True)
    CanEditModel = Column(Boolean, default=True)
    PermissionPolicy = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    ObjectType = Column(ForeignKey('xpobjecttype.OID'), index=True)

    xpobjecttype = relationship('Xpobjecttype')


class Project(Base):
    __tablename__ = 'project'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(100))
    description = Column(String(300))
    start_on = Column(DateTime)
    end_on = Column(DateTime)
    owner_id = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_party = relationship('SysSecParty')


class Site(Base):
    __tablename__ = 'site'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    address = Column(String(150))
    manager_id = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_party = relationship('SysSecParty')


class SysSecActionpermission(Base):
    __tablename__ = 'sys_sec_actionpermission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    ActionId = Column(String(100))
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecLogininfo(Base):
    __tablename__ = 'sys_sec_logininfo'
    __table_args__ = (
        Index('iLoginProviderNameProviderUserKey_sys_sec_logininfo', 'LoginProviderName', 'ProviderUserKey',
              unique=True),
    )

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    LoginProviderName = Column(String(100))
    ProviderUserKey = Column(String(100))
    User = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))

    sys_sec_party = relationship('SysSecParty')


class SysSecNavigationpermission(Base):
    __tablename__ = 'sys_sec_navigationpermission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    ItemPath = Column(Text)
    NavigateState = Column(INTEGER(11))
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecTypepermission(Base):
    __tablename__ = 'sys_sec_typepermission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    TargetType = Column(Text)
    ReadState = Column(INTEGER(11))
    WriteState = Column(INTEGER(11))
    CreateState = Column(INTEGER(11))
    DeleteState = Column(INTEGER(11))
    NavigateState = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecUserrole(Base):
    __tablename__ = 'sys_sec_userrole'
    __table_args__ = (
        Index('iPeopleRoles_sys_sec_userrole', 'People', 'Roles', unique=True),
    )

    People = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    Roles = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    OID = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    OptimisticLockField = Column(INTEGER(11))

    sys_sec_party = relationship('SysSecParty')
    sys_sec_role = relationship('SysSecRole')


class Msession(Base):
    __tablename__ = 'msession'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(50))
    project_id = Column(ForeignKey('project.Oid'), index=True)
    site_id = Column(ForeignKey('site.Oid'), index=True)
    user_id = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    description = Column(String(250))
    start_on = Column(DateTime)
    end_on = Column(DateTime)
    microscope_id = Column(ForeignKey('microscope.Oid'), index=True)
    camera_id = Column(ForeignKey('camera.Oid'), index=True)
    sample_type = Column(ForeignKey('sampletype.Oid'), index=True)
    sample_name = Column(String(50))
    sample_grid_type = Column(ForeignKey('samplegridtype.Oid'), index=True)
    sample_sequence = Column(Text)
    sample_procedure = Column(Text)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    camera = relationship('Camera')
    microscope = relationship('Microscope')
    project = relationship('Project')
    samplegridtype = relationship('Samplegridtype')
    sampletype = relationship('Sampletype')
    site = relationship('Site')
    sys_sec_party = relationship('SysSecParty')


class SysSecMemberpermission(Base):
    __tablename__ = 'sys_sec_memberpermission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Members = Column(Text)
    ReadState = Column(INTEGER(11))
    WriteState = Column(INTEGER(11))
    Criteria = Column(Text)
    TypePermissionObject = Column(ForeignKey('sys_sec_typepermission.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_typepermission = relationship('SysSecTypepermission')


class SysSecObjectpermission(Base):
    __tablename__ = 'sys_sec_objectpermission'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Criteria = Column(Text)
    ReadState = Column(INTEGER(11))
    WriteState = Column(INTEGER(11))
    DeleteState = Column(INTEGER(11))
    NavigateState = Column(INTEGER(11))
    TypePermissionObject = Column(ForeignKey('sys_sec_typepermission.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_typepermission = relationship('SysSecTypepermission')


class Ctfjob(Base):
    __tablename__ = 'ctfjob'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(100))
    description = Column(Text)
    created_on = Column(DateTime)
    start_on = Column(DateTime)
    end_on = Column(DateTime)
    user_id = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    project_id = Column(ForeignKey('project.Oid'), index=True)
    msession_id = Column(ForeignKey('msession.Oid'), index=True)
    status = Column(INTEGER(11))
    type = Column(INTEGER(11))
    settings = Column(Text)
    cs = Column(DECIMAL(28, 8))
    path = Column(String(255))
    output_dir = Column(String(255))
    direction = Column(INTEGER(11))
    image_selection_criteria = Column(Text)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    msession = relationship('Msession')
    project = relationship('Project')
    sys_sec_party = relationship('SysSecParty')


class Image(Base):
    __tablename__ = 'image'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(50))
    path = Column(String(300))
    parent_id = Column(ForeignKey('image.Oid'), index=True)
    session_id = Column(ForeignKey('msession.Oid'), index=True)
    atlas_id = Column(ForeignKey('atlas.Oid'), index=True)
    magnification = Column(BIGINT(20))
    dose = Column(DECIMAL(28, 8))
    focus = Column(DECIMAL(28, 8))
    defocus = Column(DECIMAL(28, 8))
    spot_size = Column(BIGINT(20))
    old_id = Column(BIGINT(20))
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
    pixel_size = Column(DOUBLE)
    pixel_size_x = Column(DECIMAL(28, 8))
    pixel_size_y = Column(DECIMAL(28, 8))
    energy_filtered = Column(Boolean, default=False)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    level = Column(INTEGER(11))
    atlas_delta_row = Column(DECIMAL(28, 8))
    atlas_delta_column = Column(DECIMAL(28, 8))
    atlas_dimxy = Column(DECIMAL(28, 8))
    stage_x = Column(DECIMAL(28, 8))
    stage_y = Column(DECIMAL(28, 8))
    stage_alpha_tilt = Column(DECIMAL(28, 8))

    parent = relationship('Image', remote_side=[Oid])
    msession = relationship('Msession')
    atlas = relationship('Atlas')


class ImageMetadata(Base):
    __tablename__ = 'image_meta_data'

    oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    image_id = Column(ForeignKey('image.Oid'), index=True)
    name = Column(String(100))
    # job_id = Column(ForeignKey('imagejob.Oid'), index=True)
    # task_id = Column(String(100))
    created_date = Column(DateTime)
    data = Column(LONGTEXT)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    type = Column(INTEGER(11))
    data_json = Column(JSON)

    image = relationship('Image')


class Samplematerial(Base):
    __tablename__ = 'samplematerial'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    session = Column(ForeignKey('msession.Oid'), index=True)
    name = Column(String(30))
    quantity = Column(DECIMAL(28, 8))
    note = Column(String(150))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    msession = relationship('Msession')


class Ctfjobitem(Base):
    __tablename__ = 'ctfjobitem'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    job_id = Column(ForeignKey('ctfjob.Oid'), index=True)
    image_id = Column(ForeignKey('image.Oid'), index=True)
    settings = Column(JSON)
    status = Column(INTEGER(11))
    steps = Column(INTEGER(11))
    score = Column(DECIMAL(28, 8))
    defocus1 = Column(DECIMAL(28, 8))
    defocus2 = Column(DECIMAL(28, 8))
    res50 = Column(DECIMAL(28, 8))
    res80 = Column(DECIMAL(28, 8))
    tilt_angle = Column(DECIMAL(28, 8))
    tilt_axis_angle = Column(DECIMAL(28, 8))
    phase_shift = Column(DECIMAL(28, 8))
    angle_astigmatism = Column(DECIMAL(28, 8))
    package_resolution = Column(DECIMAL(28, 8))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    image = relationship('Image')
    job = relationship('Ctfjob')


class Frametransferjob(Base):
    __tablename__ = 'frametransferjob'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(100))
    description = Column(Text)
    created_on = Column(DateTime)
    start_on = Column(DateTime)
    end_on = Column(DateTime)
    user_id = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    project_id = Column(ForeignKey('project.Oid'), index=True)
    msession_id = Column(ForeignKey('msession.Oid'), index=True)
    status = Column(INTEGER(11))
    type = Column(INTEGER(11))
    settings = Column(Text)
    cs = Column(DECIMAL(28, 8))
    path = Column(String(255))
    output_dir = Column(String(100))
    direction = Column(INTEGER(11))
    image_selection_criteria = Column(Text)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    msession = relationship('Msession')
    project = relationship('Project')
    user = relationship('SysSecParty')


class Frametransferjobitem(Base):
    __tablename__ = 'frametransferjobitem'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    job_id = Column(ForeignKey('frametransferjob.Oid'), index=True)
    image_id = Column(ForeignKey('image.Oid'), index=True)
    settings = Column(JSON)
    status = Column(INTEGER(11))
    steps = Column(INTEGER(11))
    filename = Column(Text)
    image_name = Column(Text)
    image_path = Column(Text)
    frame_name = Column(Text)
    frame_path = Column(Text)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    image = relationship('Image')
    job = relationship('Frametransferjob')


class Particlepickingjob(Base):
    __tablename__ = 'particlepickingjob'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(100))
    description = Column(Text)
    created_on = Column(DateTime)
    end_on = Column(DateTime)
    user_id = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    project_id = Column(ForeignKey('project.Oid'), index=True)
    msession_id = Column(ForeignKey('msession.Oid'), index=True)
    status = Column(INTEGER(11))
    type = Column(INTEGER(11))
    settings = Column(JSON)
    cs = Column(DECIMAL(28, 8))
    path = Column(String(255))
    output_dir = Column(String(255))
    direction = Column(INTEGER(11))
    image_selection_criteria = Column(Text)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    msession = relationship('Msession')
    project = relationship('Project')
    user = relationship('SysSecParty')


class Particlepickingjobitem(Base):
    __tablename__ = 'particlepickingjobitem'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    job_id = Column(ForeignKey('particlepickingjob.Oid'), index=True)
    image_id = Column(ForeignKey('image.Oid'), index=True)
    settings = Column(JSON)
    status = Column(INTEGER(11))
    steps = Column(INTEGER(11))
    type = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    image = relationship('Image')
    job = relationship('Particlepickingjob')


class ImageJob(Base):
    __tablename__ = 'image_job'

    Oid = Column(SqlalchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(100))
    description = Column(Text)
    created_on = Column(DateTime)
    start_on = Column(DateTime)
    end_on = Column(DateTime)
    user_id = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    project_id = Column(ForeignKey('project.Oid'), index=True)
    msession_id = Column(ForeignKey('msession.Oid'), index=True)
    status = Column(INTEGER(11))
    type = Column(INTEGER(11))
    settings = Column(LONGTEXT)
    cs = Column(DECIMAL(28, 8))
    path = Column(String(255))
    output_dir = Column(String(100))
    direction = Column(SMALLINT(5))
    image_selection_criteria = Column(Text)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    msession = relationship('Msession')
    project = relationship('Project')
    user = relationship('SysSecParty')


class ImageJobTask(Base):
    __tablename__ = 'image_job_task'

    OID = Column(INTEGER(11), primary_key=True)
    job_id = Column(ForeignKey('image_job.Oid'), index=True)
    image_id = Column(ForeignKey('image.Oid'), index=True)
    status = Column(SMALLINT(5))
    settings = Column(LONGTEXT)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    image = relationship('Image')
    job = relationship('ImageJob')
