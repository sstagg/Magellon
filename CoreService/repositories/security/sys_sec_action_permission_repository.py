"""
Repository for sys_sec_action_permission table operations
"""
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from models.sqlalchemy_models import SysSecActionPermission, SysSecRole
import logging

logger = logging.getLogger(__name__)


class SysSecActionPermissionRepository:
    """Repository for managing action permissions"""

    @staticmethod
    def create(db: Session, role_id: UUID, action_id: str) -> SysSecActionPermission:
        """
        Create an action permission for a role
        """
        try:
            # Check if permission already exists
            existing = SysSecActionPermissionRepository.fetch_by_role_and_action(
                db, role_id, action_id
            )
            if existing:
                return existing

            permission = SysSecActionPermission(
                Oid=uuid4(),
                ActionId=action_id,
                Role=role_id,
                OptimisticLockField=0
            )

            db.add(permission)
            db.commit()
            db.refresh(permission)
            return permission

        except Exception as e:
            db.rollback()
            logger.exception("Error creating action permission")
            raise e

    @staticmethod
    def fetch_by_role_and_action(db: Session, role_id: UUID, action_id: str) -> Optional[SysSecActionPermission]:
        """
        Fetch action permission by role and action ID
        """
        return db.query(SysSecActionPermission).filter(
            and_(
                SysSecActionPermission.Role == role_id,
                SysSecActionPermission.ActionId == action_id
            )
        ).first()

    @staticmethod
    def fetch_by_role(db: Session, role_id: UUID) -> List[SysSecActionPermission]:
        """
        Fetch all action permissions for a role
        """
        return db.query(SysSecActionPermission).filter(
            SysSecActionPermission.Role == role_id
        ).order_by(SysSecActionPermission.ActionId).all()

    @staticmethod
    def fetch_by_action(db: Session, action_id: str) -> List[SysSecActionPermission]:
        """
        Fetch all roles that have permission for a specific action
        """
        return db.query(SysSecActionPermission).options(
            joinedload(SysSecActionPermission.sys_sec_role)
        ).join(
            SysSecRole, SysSecActionPermission.Role == SysSecRole.Oid
        ).filter(
            and_(
                SysSecActionPermission.ActionId == action_id,
                SysSecRole.GCRecord.is_(None)
            )
        ).order_by(SysSecRole.Name).all()

    @staticmethod
    def delete(db: Session, permission_id: UUID) -> bool:
        """
        Delete an action permission
        """
        try:
            permission = db.query(SysSecActionPermission).filter(
                SysSecActionPermission.Oid == permission_id
            ).first()

            if not permission:
                return False

            db.delete(permission)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting action permission")
            raise e

    @staticmethod
    def delete_by_role_and_action(db: Session, role_id: UUID, action_id: str) -> bool:
        """
        Delete action permission by role and action
        """
        try:
            permission = db.query(SysSecActionPermission).filter(
                and_(
                    SysSecActionPermission.Role == role_id,
                    SysSecActionPermission.ActionId == action_id
                )
            ).first()

            if not permission:
                return False

            db.delete(permission)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting action permission")
            raise e

    @staticmethod
    def delete_all_for_role(db: Session, role_id: UUID) -> bool:
        """
        Delete all action permissions for a role
        """
        try:
            db.query(SysSecActionPermission).filter(
                SysSecActionPermission.Role == role_id
            ).delete()
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting role permissions")
            raise e

    @staticmethod
    def bulk_create(db: Session, role_id: UUID, action_ids: List[str]) -> List[str]:
        """
        Create multiple action permissions for a role
        """
        try:
            # Get existing permissions to avoid duplicates
            existing_actions = {
                perm.ActionId for perm in db.query(SysSecActionPermission).filter(
                    and_(
                        SysSecActionPermission.Role == role_id,
                        SysSecActionPermission.ActionId.in_(action_ids)
                    )
                ).all()
            }

            # Filter out existing permissions
            new_action_ids = [aid for aid in action_ids if aid not in existing_actions]

            if not new_action_ids:
                return []

            # Bulk insert
            new_permissions = [
                SysSecActionPermission(
                    Oid=uuid4(),
                    ActionId=action_id,
                    Role=role_id,
                    OptimisticLockField=0
                )
                for action_id in new_action_ids
            ]

            db.add_all(new_permissions)
            db.commit()
            return new_action_ids

        except Exception as e:
            db.rollback()
            logger.exception("Error in bulk create action permissions")
            raise e

    @staticmethod
    def fetch_all_actions(db: Session) -> List[str]:
        """
        Fetch all distinct action IDs from the system
        """
        results = db.query(SysSecActionPermission.ActionId).distinct().order_by(
            SysSecActionPermission.ActionId
        ).all()
        return [row[0] for row in results]

    @staticmethod
    def count_permissions_for_role(db: Session, role_id: UUID) -> int:
        """
        Count action permissions for a role
        """
        return db.query(SysSecActionPermission).filter(
            SysSecActionPermission.Role == role_id
        ).count()
