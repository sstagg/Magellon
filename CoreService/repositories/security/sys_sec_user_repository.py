import uuid
from datetime import datetime
from uuid import UUID
from typing import Optional, List

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from passlib.context import CryptContext

from models.pydantic_models import SysSecUserCreateDto, SysSecUserUpdateDto
from models.sqlalchemy_models import SysSecUser

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SysSecUserRepository:

    @staticmethod
    async def create(db: Session, user_dto: SysSecUserCreateDto, created_by: Optional[UUID] = None) -> SysSecUser:
        """
        Create a new user record

        Args:
            db: Database session
            user_dto: User creation data
            created_by: UUID of the user creating this record

        Returns:
            Created SysSecUser instance
        """
        user_oid = uuid.uuid4()
        current_time = datetime.now()

        user = SysSecUser(
            oid=user_oid,
            omid=user_dto.omid,
            ouid=user_dto.ouid,
            created_date=current_time,
            created_by=created_by,
            last_modified_date=current_time,
            last_modified_by=created_by,
            sync_status=user_dto.sync_status,
            version=user_dto.version,
            PASSWORD=user_dto.password,  # Note: Should be hashed before this point
            ChangePasswordOnFirstLogon=user_dto.change_password_on_first_logon,
            USERNAME=user_dto.username,
            ACTIVE=user_dto.active,
            OptimisticLockField=1,
            ObjectType=user_dto.object_type,
            AccessFailedCount=0
        )

        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def fetch_by_id(db: Session, user_id: UUID) -> Optional[SysSecUser]:
        """Get user by ID"""
        return db.query(SysSecUser).filter(
            and_(
                SysSecUser.oid == user_id,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

    @staticmethod
    def fetch_by_username(db: Session, username: str) -> Optional[SysSecUser]:
        """Get user by username"""
        return db.query(SysSecUser).filter(
            and_(
                SysSecUser.USERNAME == username,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

    @staticmethod
    def fetch_active_by_username(db: Session, username: str) -> Optional[SysSecUser]:
        """Get active user by username"""
        return db.query(SysSecUser).filter(
            and_(
                SysSecUser.USERNAME == username,
                SysSecUser.ACTIVE == True,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[SysSecUser]:
        """
        Authenticate user with username and password

        Args:
            db: Database session
            username: Username to authenticate
            password: Plain text password to verify

        Returns:
            SysSecUser if authentication successful, None otherwise
        """
        # Fetch active user by username
        user = SysSecUserRepository.fetch_active_by_username(db, username)

        if not user:
            return None

        # Check if user is locked out
        if user.LockoutEnd and user.LockoutEnd > datetime.now():
            return None

        # Verify password
        if not pwd_context.verify(password, user.PASSWORD):
            return None

        return user

    @staticmethod
    def fetch_all(db: Session, skip: int = 0, limit: int = 100, include_inactive: bool = False) -> List[SysSecUser]:
        """Get all users with pagination"""
        query = db.query(SysSecUser).filter(SysSecUser.GCRecord.is_(None))

        if not include_inactive:
            query = query.filter(SysSecUser.ACTIVE == True)

        return query.offset(skip).limit(limit).all()

    @staticmethod
    def search_by_username(db: Session, username_pattern: str, skip: int = 0, limit: int = 100) -> List[SysSecUser]:
        """Search users by username pattern"""
        return db.query(SysSecUser).filter(
            and_(
                SysSecUser.USERNAME.like(f"%{username_pattern}%"),
                SysSecUser.GCRecord.is_(None)
            )
        ).offset(skip).limit(limit).all()

    @staticmethod
    async def update(db: Session, user_dto: SysSecUserUpdateDto, updated_by: Optional[UUID] = None) -> Optional[SysSecUser]:
        """Update user record"""
        user = db.query(SysSecUser).filter(
            and_(
                SysSecUser.oid == user_dto.oid,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

        if not user:
            return None

        # Update fields if provided
        if user_dto.username is not None:
            user.USERNAME = user_dto.username
        if user_dto.password is not None:
            user.PASSWORD = user_dto.password  # Should be hashed
        if user_dto.active is not None:
            user.ACTIVE = user_dto.active
        if user_dto.change_password_on_first_logon is not None:
            user.ChangePasswordOnFirstLogon = user_dto.change_password_on_first_logon
        if user_dto.omid is not None:
            user.omid = user_dto.omid
        if user_dto.ouid is not None:
            user.ouid = user_dto.ouid
        if user_dto.sync_status is not None:
            user.sync_status = user_dto.sync_status
        if user_dto.version is not None:
            user.version = user_dto.version
        if user_dto.object_type is not None:
            user.ObjectType = user_dto.object_type
        if user_dto.access_failed_count is not None:
            user.AccessFailedCount = user_dto.access_failed_count
        if user_dto.lockout_end is not None:
            user.LockoutEnd = user_dto.lockout_end

        # Always update modification tracking
        user.last_modified_date = datetime.now()
        user.last_modified_by = updated_by

        # Increment optimistic lock field
        if user.OptimisticLockField:
            user.OptimisticLockField += 1
        else:
            user.OptimisticLockField = 1

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    async def soft_delete(db: Session, user_id: UUID, deleted_by: Optional[UUID] = None) -> bool:
        """Soft delete user by setting GCRecord"""
        user = db.query(SysSecUser).filter(
            and_(
                SysSecUser.oid == user_id,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

        if not user:
            return False

        # Mark as deleted
        user.GCRecord = 1
        user.deleted_date = datetime.now()
        user.deleted_by = deleted_by
        user.last_modified_date = datetime.now()
        user.last_modified_by = deleted_by

        db.commit()
        return True

    @staticmethod
    async def hard_delete(db: Session, user_id: UUID) -> bool:
        """Permanently delete user record"""
        user = db.query(SysSecUser).filter(SysSecUser.oid == user_id).first()

        if not user:
            return False

        db.delete(user)
        db.commit()
        return True

    @staticmethod
    async def increment_failed_access(db: Session, user_id: UUID) -> Optional[SysSecUser]:
        """Increment failed access count"""
        user = db.query(SysSecUser).filter(
            and_(
                SysSecUser.oid == user_id,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

        if not user:
            return None

        user.AccessFailedCount = (user.AccessFailedCount or 0) + 1
        user.last_modified_date = datetime.now()

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    async def reset_failed_access(db: Session, user_id: UUID) -> Optional[SysSecUser]:
        """Reset failed access count"""
        user = db.query(SysSecUser).filter(
            and_(
                SysSecUser.oid == user_id,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

        if not user:
            return None

        user.AccessFailedCount = 0
        user.LockoutEnd = None
        user.last_modified_date = datetime.now()

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    async def set_lockout(db: Session, user_id: UUID, lockout_end: datetime) -> Optional[SysSecUser]:
        """Set user lockout end time"""
        user = db.query(SysSecUser).filter(
            and_(
                SysSecUser.oid == user_id,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

        if not user:
            return None

        user.LockoutEnd = lockout_end
        user.last_modified_date = datetime.now()

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def is_locked_out(db: Session, user_id: UUID) -> bool:
        """Check if user is currently locked out"""
        user = db.query(SysSecUser).filter(
            and_(
                SysSecUser.oid == user_id,
                SysSecUser.GCRecord.is_(None)
            )
        ).first()

        if not user or not user.LockoutEnd:
            return False

        return user.LockoutEnd > datetime.now()

    @staticmethod
    def count_users(db: Session, include_inactive: bool = False) -> int:
        """Count total users"""
        query = db.query(SysSecUser).filter(SysSecUser.GCRecord.is_(None))

        if not include_inactive:
            query = query.filter(SysSecUser.ACTIVE == True)

        return query.count()