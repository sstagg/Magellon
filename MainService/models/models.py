# coding: utf-8
import uuid

from sqlalchemy import BINARY, Column, DECIMAL, ForeignKey, Index, String, Text, Boolean, LargeBinary, DateTime
from sqlalchemy.dialects.mysql import BIGINT,  INTEGER
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils import UUIDType

from lib.alchemy_uuid import SqlAlchemyUuidType

Base = declarative_base()
metadata = Base.metadata


class Camera(Base):
    __tablename__ = 'camera'

    # Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    Oid = Column(UUIDType, primary_key=True, default=uuid.uuid4, unique=True)  # UUIDType
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Microscope(Base):
    __tablename__ = 'microscope'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Modeldifference(Base):
    __tablename__ = 'modeldifference'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    UserId = Column(String(100))
    ContextId = Column(String(100))
    Version = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Samplegridtype(Base):
    __tablename__ = 'samplegridtype'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)


class Sampletype(Base):
    __tablename__ = 'sampletype'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
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

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Name = Column(String(100))
    Xml = Column(Text)
    Owner = Column(ForeignKey('modeldifference.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    modeldifference = relationship('Modeldifference')


class SysSecParty(Base):
    __tablename__ = 'sys_sec_party'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
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
    ChangePasswordOnFirstLogon = Column(Boolean,default=True)
    UserName = Column(String(100))
    IsActive = Column(Boolean,default= True)
    photo = Column(LargeBinary)

    xpobjecttype = relationship('Xpobjecttype')
    parent = relationship('SysSecParty', remote_side=[Oid], primaryjoin='SysSecParty.createdBy == SysSecParty.Oid')
    parent1 = relationship('SysSecParty', remote_side=[Oid], primaryjoin='SysSecParty.lastModifiedBy == SysSecParty.Oid')


class SysSecRole(Base):
    __tablename__ = 'sys_sec_role'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Name = Column(String(100))
    IsAdministrative = Column(Boolean,default= True)
    CanEditModel = Column(Boolean,default= True)
    PermissionPolicy = Column(INTEGER(11))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)
    ObjectType = Column(ForeignKey('xpobjecttype.OID'), index=True)

    xpobjecttype = relationship('Xpobjecttype')


class Project(Base):
    __tablename__ = 'project'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    description = Column(String(200))
    startOn = Column(DateTime)
    endOn = Column(DateTime)
    owner = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_party = relationship('SysSecParty')


class Site(Base):
    __tablename__ = 'site'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    address = Column(String(150))
    manager = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_party = relationship('SysSecParty')


class SysSecActionpermission(Base):
    __tablename__ = 'sys_sec_actionpermission'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    ActionId = Column(String(100))
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecLogininfo(Base):
    __tablename__ = 'sys_sec_logininfo'
    __table_args__ = (
        Index('iLoginProviderNameProviderUserKey_sys_sec_logininfo', 'LoginProviderName', 'ProviderUserKey', unique=True),
    )

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    LoginProviderName = Column(String(100))
    ProviderUserKey = Column(String(100))
    User = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))

    sys_sec_party = relationship('SysSecParty')


class SysSecNavigationpermission(Base):
    __tablename__ = 'sys_sec_navigationpermission'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    ItemPath = Column(Text)
    NavigateState = Column(INTEGER(11))
    Role = Column(ForeignKey('sys_sec_role.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_role = relationship('SysSecRole')


class SysSecTypepermission(Base):
    __tablename__ = 'sys_sec_typepermission'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
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
    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    OptimisticLockField = Column(INTEGER(11))

    sys_sec_party = relationship('SysSecParty')
    sys_sec_role = relationship('SysSecRole')


class Msession(Base):
    __tablename__ = 'msession'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    name = Column(String(30))
    project = Column(ForeignKey('project.Oid'), index=True)
    site = Column(ForeignKey('site.Oid'), index=True)
    user = Column(ForeignKey('sys_sec_party.Oid'), index=True)
    description = Column(String(150))
    startOn = Column(DateTime)
    endOn = Column(DateTime)
    microscope = Column(ForeignKey('microscope.Oid'), index=True)
    camera = Column(ForeignKey('camera.Oid'), index=True)
    sampleType = Column(ForeignKey('sampletype.Oid'), index=True)
    sampleName = Column(String(30))
    sampleGridType = Column(ForeignKey('samplegridtype.Oid'), index=True)
    sampleSequence = Column(String(150))
    sampleProcedure = Column(Text)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    camera1 = relationship('Camera')
    microscope1 = relationship('Microscope')
    project1 = relationship('Project')
    samplegridtype = relationship('Samplegridtype')
    sampletype = relationship('Sampletype')
    site1 = relationship('Site')
    sys_sec_party = relationship('SysSecParty')
    images = relationship('Image', back_populates='msession')

class SysSecMemberpermission(Base):
    __tablename__ = 'sys_sec_memberpermission'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
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

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    Criteria = Column(Text)
    ReadState = Column(INTEGER(11))
    WriteState = Column(INTEGER(11))
    DeleteState = Column(INTEGER(11))
    NavigateState = Column(INTEGER(11))
    TypePermissionObject = Column(ForeignKey('sys_sec_typepermission.Oid'), index=True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    sys_sec_typepermission = relationship('SysSecTypepermission')


class Image(Base):
    __tablename__ = 'image'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    # original = Column(LargeBinary)
    # aligned = Column(LargeBinary)
    # fft = Column(LargeBinary)
    # ctf = Column(LargeBinary)
    Name = Column(String(30))
    path = Column(String(100))
    parent = Column(ForeignKey('image.Oid'), index=True)
    session = Column(ForeignKey('msession.Oid'), index=True)
    mag = Column(BIGINT(20))
    focus = Column(DECIMAL(28, 8))
    defocus = Column(DECIMAL(28, 8))
    spotSize = Column(BIGINT(20))
    intensity = Column(DECIMAL(28, 8))
    shiftX = Column(DECIMAL(28, 8))
    shiftY = Column(DECIMAL(28, 8))
    beamShiftX = Column(DECIMAL(28, 8))
    beamShiftY = Column(DECIMAL(28, 8))
    resetFocus = Column(BIGINT(20))
    screenCurrent = Column(BIGINT(20))
    beamBank = Column(String(150))
    condenserX = Column(DECIMAL(28, 8))
    condenserY = Column(DECIMAL(28, 8))
    objectiveX = Column(DECIMAL(28, 8))
    objectiveY = Column(DECIMAL(28, 8))
    dimensionX = Column(BIGINT(20))
    dimensionY = Column(BIGINT(20))
    binningX = Column(BIGINT(20))
    binningY = Column(BIGINT(20))
    offsetX = Column(BIGINT(20))
    offsetY = Column(BIGINT(20))
    exposureTime = Column(DECIMAL(28, 8))
    exposureType = Column(BIGINT(20))
    pixelSizeX = Column(DECIMAL(28, 8))
    pixelSizeY = Column(DECIMAL(28, 8))
    energyFiltered = Column(Boolean,default= True)
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    parent1 = relationship('Image', remote_side=[Oid])
    msession = relationship('Msession')


class Samplebom(Base):
    __tablename__ = 'samplebom'

    Oid = Column(SqlAlchemyUuidType, primary_key=True, default=uuid.uuid4, unique=True)
    session = Column(ForeignKey('msession.Oid'), index=True)
    name = Column(String(30))
    quantity = Column(DECIMAL(28, 8))
    note = Column(String(150))
    OptimisticLockField = Column(INTEGER(11))
    GCRecord = Column(INTEGER(11), index=True)

    msession = relationship('Msession')
