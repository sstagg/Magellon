"""
Object Permission Repository

Handles database operations for object-level permissions (record-based permissions).
Object permissions define criteria-based access control for specific instances of entities.

Based on XAF security system pattern.
"""
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.sqlalchemy_models import SysSecObjectPermission
import logging

logger = logging.getLogger(__name__)


class SysSecObjectPermissionRepository:
    """
    Repository for sys_sec_object_permission table operations.
    Manages criteria-based record-level permissions.
    """

    @staticmethod
    def fetch_all(db: Session, include_deleted: bool = False) -> List[SysSecObjectPermission]:
        """
        Fetch all object permissions.

        Args:
            db: Database session
            include_deleted: Include soft-deleted records

        Returns:
            List of object permission records
        """
        query = db.query(SysSecObjectPermission)

        if not include_deleted:
            query = query.filter(SysSecObjectPermission.GCRecord.is_(None))

        return query.all()

    @staticmethod
    def fetch_by_id(db: Session, permission_id: UUID) -> Optional[SysSecObjectPermission]:
        """
        Fetch object permission by ID.

        Args:
            db: Database session
            permission_id: Permission UUID

        Returns:
            Object permission record or None
        """
        return db.query(SysSecObjectPermission).filter(
            and_(
                SysSecObjectPermission.oid == permission_id,
                SysSecObjectPermission.GCRecord.is_(None)
            )
        ).first()

    @staticmethod
    def fetch_by_type_permission(
        db: Session,
        type_permission_id: UUID,
        include_deleted: bool = False
    ) -> List[SysSecObjectPermission]:
        """
        Fetch all object permissions for a specific type permission.

        Args:
            db: Database session
            type_permission_id: Parent type permission UUID
            include_deleted: Include soft-deleted records

        Returns:
            List of object permission records
        """
        query = db.query(SysSecObjectPermission).filter(
            SysSecObjectPermission.TypePermissionObject == type_permission_id
        )

        if not include_deleted:
            query = query.filter(SysSecObjectPermission.GCRecord.is_(None))

        return query.all()

    @staticmethod
    def create(
        db: Session,
        type_permission_id: UUID,
        criteria: str,
        read_state: int = 0,
        write_state: int = 0,
        delete_state: int = 0,
        navigate_state: int = 0
    ) -> SysSecObjectPermission:
        """
        Create a new object permission.

        Args:
            db: Database session
            type_permission_id: Parent type permission UUID
            criteria: XAF-style criteria expression
            read_state: Read permission (0=Deny, 1=Allow)
            write_state: Write permission (0=Deny, 1=Allow)
            delete_state: Delete permission (0=Deny, 1=Allow)
            navigate_state: Navigate permission (0=Deny, 1=Allow)

        Returns:
            Created object permission record
        """
        permission = SysSecObjectPermission(
            oid=uuid4(),
            TypePermissionObject=type_permission_id,
            Criteria=criteria,
            ReadState=read_state,
            WriteState=write_state,
            DeleteState=delete_state,
            NavigateState=navigate_state,
            OptimisticLockField=0,
            GCRecord=None
        )

        db.add(permission)
        db.commit()
        db.refresh(permission)

        logger.info(f"Created object permission: {permission.oid} for type permission: {type_permission_id}")

        return permission

    @staticmethod
    def update(
        db: Session,
        permission_id: UUID,
        criteria: Optional[str] = None,
        read_state: Optional[int] = None,
        write_state: Optional[int] = None,
        delete_state: Optional[int] = None,
        navigate_state: Optional[int] = None
    ) -> Optional[SysSecObjectPermission]:
        """
        Update an object permission.

        Args:
            db: Database session
            permission_id: Permission UUID
            criteria: Updated criteria expression
            read_state: Updated read permission
            write_state: Updated write permission
            delete_state: Updated delete permission
            navigate_state: Updated navigate permission

        Returns:
            Updated object permission record or None
        """
        permission = SysSecObjectPermissionRepository.fetch_by_id(db, permission_id)

        if not permission:
            logger.warning(f"Object permission not found: {permission_id}")
            return None

        # Update fields if provided
        if criteria is not None:
            permission.Criteria = criteria

        if read_state is not None:
            permission.ReadState = read_state

        if write_state is not None:
            permission.WriteState = write_state

        if delete_state is not None:
            permission.DeleteState = delete_state

        if navigate_state is not None:
            permission.NavigateState = navigate_state

        # Increment optimistic lock field
        permission.OptimisticLockField = (permission.OptimisticLockField or 0) + 1

        db.commit()
        db.refresh(permission)

        logger.info(f"Updated object permission: {permission_id}")

        return permission

    @staticmethod
    def update_operations(
        db: Session,
        permission_id: UUID,
        read_state: Optional[int] = None,
        write_state: Optional[int] = None,
        delete_state: Optional[int] = None,
        navigate_state: Optional[int] = None
    ) -> Optional[SysSecObjectPermission]:
        """
        Update only the operation states (read/write/delete/navigate).

        Args:
            db: Database session
            permission_id: Permission UUID
            read_state: Read permission
            write_state: Write permission
            delete_state: Delete permission
            navigate_state: Navigate permission

        Returns:
            Updated object permission record or None
        """
        return SysSecObjectPermissionRepository.update(
            db=db,
            permission_id=permission_id,
            read_state=read_state,
            write_state=write_state,
            delete_state=delete_state,
            navigate_state=navigate_state
        )

    @staticmethod
    def delete(db: Session, permission_id: UUID, hard_delete: bool = False) -> bool:
        """
        Delete an object permission (soft delete by default).

        Args:
            db: Database session
            permission_id: Permission UUID
            hard_delete: If True, permanently delete from database

        Returns:
            True if deleted, False if not found
        """
        permission = SysSecObjectPermissionRepository.fetch_by_id(db, permission_id)

        if not permission:
            logger.warning(f"Object permission not found: {permission_id}")
            return False

        if hard_delete:
            # Permanent deletion
            db.delete(permission)
            logger.info(f"Hard deleted object permission: {permission_id}")
        else:
            # Soft delete (set GCRecord)
            permission.GCRecord = 1
            logger.info(f"Soft deleted object permission: {permission_id}")

        db.commit()

        return True

    @staticmethod
    def count_by_type_permission(db: Session, type_permission_id: UUID) -> int:
        """
        Count object permissions for a specific type permission.

        Args:
            db: Database session
            type_permission_id: Parent type permission UUID

        Returns:
            Count of object permissions
        """
        return db.query(SysSecObjectPermission).filter(
            and_(
                SysSecObjectPermission.TypePermissionObject == type_permission_id,
                SysSecObjectPermission.GCRecord.is_(None)
            )
        ).count()
