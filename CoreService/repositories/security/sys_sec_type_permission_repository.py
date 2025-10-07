"""
Repository for sys_sec_type_permission table operations
"""
from typing import List, Optional, Dict
from uuid import UUID, uuid4

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from models.sqlalchemy_models import SysSecTypePermission, SysSecRole
import logging

logger = logging.getLogger(__name__)


class SysSecTypePermissionRepository:
    """Repository for managing type/object permissions"""

    @staticmethod
    def create(
        db: Session,
        role_id: UUID,
        target_type: str,
        read_state: int = 0,
        write_state: int = 0,
        create_state: int = 0,
        delete_state: int = 0,
        navigate_state: int = 0
    ) -> SysSecTypePermission:
        """
        Create a type permission for a role
        States: 0 = Deny, 1 = Allow
        """
        try:
            # Check if permission already exists
            existing = SysSecTypePermissionRepository.fetch_by_role_and_type(
                db, role_id, target_type
            )
            if existing:
                return existing

            permission = SysSecTypePermission(
                Oid=uuid4(),
                TargetType=target_type,
                Role=role_id,
                ReadState=read_state,
                WriteState=write_state,
                CreateState=create_state,
                DeleteState=delete_state,
                NavigateState=navigate_state,
                OptimisticLockField=0
            )

            db.add(permission)
            db.commit()
            db.refresh(permission)
            return permission

        except Exception as e:
            db.rollback()
            logger.exception("Error creating type permission")
            raise e

    @staticmethod
    def update(
        db: Session,
        permission_id: UUID,
        read_state: Optional[int] = None,
        write_state: Optional[int] = None,
        create_state: Optional[int] = None,
        delete_state: Optional[int] = None,
        navigate_state: Optional[int] = None
    ) -> Optional[SysSecTypePermission]:
        """
        Update type permission states
        """
        try:
            permission = db.query(SysSecTypePermission).filter(
                SysSecTypePermission.Oid == permission_id
            ).first()

            if not permission:
                return None

            # Update fields if provided
            if read_state is not None:
                permission.ReadState = read_state
            if write_state is not None:
                permission.WriteState = write_state
            if create_state is not None:
                permission.CreateState = create_state
            if delete_state is not None:
                permission.DeleteState = delete_state
            if navigate_state is not None:
                permission.NavigateState = navigate_state

            # Increment optimistic lock
            if permission.OptimisticLockField:
                permission.OptimisticLockField += 1
            else:
                permission.OptimisticLockField = 1

            db.commit()
            db.refresh(permission)
            return permission

        except Exception as e:
            db.rollback()
            logger.exception("Error updating type permission")
            raise e

    @staticmethod
    def fetch_by_id(db: Session, permission_id: UUID) -> Optional[SysSecTypePermission]:
        """
        Fetch type permission by ID
        """
        return db.query(SysSecTypePermission).filter(
            SysSecTypePermission.Oid == permission_id
        ).first()

    @staticmethod
    def fetch_by_role_and_type(db: Session, role_id: UUID, target_type: str) -> Optional[SysSecTypePermission]:
        """
        Fetch type permission by role and target type
        """
        return db.query(SysSecTypePermission).filter(
            and_(
                SysSecTypePermission.Role == role_id,
                SysSecTypePermission.TargetType == target_type
            )
        ).first()

    @staticmethod
    def fetch_by_role(db: Session, role_id: UUID) -> List[SysSecTypePermission]:
        """
        Fetch all type permissions for a role
        """
        return db.query(SysSecTypePermission).filter(
            SysSecTypePermission.Role == role_id
        ).order_by(SysSecTypePermission.TargetType).all()

    @staticmethod
    def fetch_by_type(db: Session, target_type: str) -> List[SysSecTypePermission]:
        """
        Fetch all roles that have permissions for a specific type
        """
        return db.query(SysSecTypePermission).options(
            joinedload(SysSecTypePermission.sys_sec_role)
        ).join(
            SysSecRole, SysSecTypePermission.Role == SysSecRole.Oid
        ).filter(
            and_(
                SysSecTypePermission.TargetType == target_type,
                SysSecRole.GCRecord.is_(None)
            )
        ).order_by(SysSecRole.Name).all()

    @staticmethod
    def delete(db: Session, permission_id: UUID) -> bool:
        """
        Delete a type permission
        """
        try:
            permission = db.query(SysSecTypePermission).filter(
                SysSecTypePermission.Oid == permission_id
            ).first()

            if not permission:
                return False

            db.delete(permission)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting type permission")
            raise e

    @staticmethod
    def delete_by_role_and_type(db: Session, role_id: UUID, target_type: str) -> bool:
        """
        Delete type permission by role and type
        """
        try:
            permission = db.query(SysSecTypePermission).filter(
                and_(
                    SysSecTypePermission.Role == role_id,
                    SysSecTypePermission.TargetType == target_type
                )
            ).first()

            if not permission:
                return False

            db.delete(permission)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting type permission")
            raise e

    @staticmethod
    def delete_all_for_role(db: Session, role_id: UUID) -> bool:
        """
        Delete all type permissions for a role
        """
        try:
            db.query(SysSecTypePermission).filter(
                SysSecTypePermission.Role == role_id
            ).delete()
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting role type permissions")
            raise e

    @staticmethod
    def fetch_all_types(db: Session) -> List[str]:
        """
        Fetch all distinct target types from the system
        """
        results = db.query(SysSecTypePermission.TargetType).distinct().order_by(
            SysSecTypePermission.TargetType
        ).all()
        return [row[0] for row in results]

    @staticmethod
    def count_permissions_for_role(db: Session, role_id: UUID) -> int:
        """
        Count type permissions for a role
        """
        return db.query(SysSecTypePermission).filter(
            SysSecTypePermission.Role == role_id
        ).count()

    @staticmethod
    def grant_full_access(db: Session, role_id: UUID, target_type: str) -> SysSecTypePermission:
        """
        Grant full access (all operations) for a type to a role
        """
        return SysSecTypePermissionRepository.create(
            db, role_id, target_type,
            read_state=1,
            write_state=1,
            create_state=1,
            delete_state=1,
            navigate_state=1
        )

    @staticmethod
    def grant_read_only(db: Session, role_id: UUID, target_type: str) -> SysSecTypePermission:
        """
        Grant read-only access for a type to a role
        """
        return SysSecTypePermissionRepository.create(
            db, role_id, target_type,
            read_state=1,
            write_state=0,
            create_state=0,
            delete_state=0,
            navigate_state=1
        )
