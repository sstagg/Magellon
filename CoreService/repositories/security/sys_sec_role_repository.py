"""
Repository for sys_sec_role table operations
"""
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from models.security.security_models import (
    RoleCreateDto,
    RoleUpdateDto,
    RoleResponseDto
)
from models.sqlalchemy_models import SysSecRole
import logging

logger = logging.getLogger(__name__)


class SysSecRoleRepository:
    """Repository for managing security roles"""

    @staticmethod
    def create(db: Session, role_dto: RoleCreateDto, created_by: Optional[UUID] = None) -> SysSecRole:
        """
        Create a new role
        """
        try:
            role = SysSecRole(
                Oid=uuid4(),
                Name=role_dto.name,
                IsAdministrative=role_dto.is_administrative,
                CanEditModel=role_dto.can_edit_model,
                PermissionPolicy=role_dto.permission_policy,
                OptimisticLockField=0,
                GCRecord=None
            )

            db.add(role)
            db.commit()
            db.refresh(role)
            return role

        except Exception as e:
            db.rollback()
            logger.exception("Error creating role")
            raise e

    @staticmethod
    def update(db: Session, role_dto: RoleUpdateDto, updated_by: Optional[UUID] = None) -> Optional[SysSecRole]:
        """
        Update an existing role
        """
        try:
            role = db.query(SysSecRole).filter(
                and_(
                    SysSecRole.Oid == role_dto.oid,
                    SysSecRole.GCRecord.is_(None)
                )
            ).first()

            if not role:
                return None

            # Update fields if provided
            if role_dto.name is not None:
                role.Name = role_dto.name
            if role_dto.is_administrative is not None:
                role.IsAdministrative = role_dto.is_administrative
            if role_dto.can_edit_model is not None:
                role.CanEditModel = role_dto.can_edit_model
            if role_dto.permission_policy is not None:
                role.PermissionPolicy = role_dto.permission_policy

            # Increment optimistic lock
            if role.OptimisticLockField:
                role.OptimisticLockField += 1
            else:
                role.OptimisticLockField = 1

            db.commit()
            db.refresh(role)
            return role

        except Exception as e:
            db.rollback()
            logger.exception("Error updating role")
            raise e

    @staticmethod
    def fetch_by_id(db: Session, role_id: UUID) -> Optional[SysSecRole]:
        """
        Fetch role by ID
        """
        return db.query(SysSecRole).filter(
            and_(
                SysSecRole.Oid == role_id,
                SysSecRole.GCRecord.is_(None)
            )
        ).first()

    @staticmethod
    def fetch_by_name(db: Session, name: str) -> Optional[SysSecRole]:
        """
        Fetch role by name
        """
        return db.query(SysSecRole).filter(
            and_(
                SysSecRole.Name == name,
                SysSecRole.GCRecord.is_(None)
            )
        ).first()

    @staticmethod
    def fetch_all(db: Session, skip: int = 0, limit: int = 100) -> List[SysSecRole]:
        """
        Fetch all roles with pagination
        """
        return db.query(SysSecRole).filter(
            SysSecRole.GCRecord.is_(None)
        ).order_by(SysSecRole.Name).offset(skip).limit(limit).all()

    @staticmethod
    def search_by_name(db: Session, name_pattern: str, skip: int = 0, limit: int = 100) -> List[SysSecRole]:
        """
        Search roles by name pattern
        """
        return db.query(SysSecRole).filter(
            and_(
                SysSecRole.Name.like(f"%{name_pattern}%"),
                SysSecRole.GCRecord.is_(None)
            )
        ).order_by(SysSecRole.Name).offset(skip).limit(limit).all()

    @staticmethod
    async def soft_delete(db: Session, role_id: UUID, deleted_by: Optional[UUID] = None) -> bool:
        """
        Soft delete role by setting GCRecord
        """
        try:
            role = db.query(SysSecRole).filter(
                and_(
                    SysSecRole.Oid == role_id,
                    SysSecRole.GCRecord.is_(None)
                )
            ).first()

            if not role:
                return False

            # Mark as deleted
            role.GCRecord = 1

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error soft deleting role")
            raise e

    @staticmethod
    async def hard_delete(db: Session, role_id: UUID) -> bool:
        """
        Permanently delete role
        """
        try:
            role = db.query(SysSecRole).filter(SysSecRole.Oid == role_id).first()

            if not role:
                return False

            db.delete(role)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error hard deleting role")
            raise e

    @staticmethod
    def count_roles(db: Session) -> int:
        """
        Count total roles
        """
        return db.query(SysSecRole).filter(
            SysSecRole.GCRecord.is_(None)
        ).count()

    @staticmethod
    def fetch_administrative_roles(db: Session) -> List[SysSecRole]:
        """
        Fetch all administrative roles
        """
        return db.query(SysSecRole).filter(
            and_(
                SysSecRole.IsAdministrative == True,
                SysSecRole.GCRecord.is_(None)
            )
        ).order_by(SysSecRole.Name).all()
