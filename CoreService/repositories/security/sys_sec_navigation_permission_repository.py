"""
Repository for sys_sec_navigation_permission table operations
"""
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from models.sqlalchemy_models import SysSecNavigationPermission, SysSecRole
import logging

logger = logging.getLogger(__name__)


class SysSecNavigationPermissionRepository:
    """Repository for managing navigation permissions"""

    @staticmethod
    def create(db: Session, role_id: UUID, item_path: str, navigate_state: int = 1) -> SysSecNavigationPermission:
        """
        Create a navigation permission for a role
        navigate_state: 0 = Deny, 1 = Allow
        """
        try:
            # Check if permission already exists
            existing = SysSecNavigationPermissionRepository.fetch_by_role_and_path(
                db, role_id, item_path
            )
            if existing:
                return existing

            permission = SysSecNavigationPermission(
                Oid=uuid4(),
                ItemPath=item_path,
                NavigateState=navigate_state,
                Role=role_id,
                OptimisticLockField=0
            )

            db.add(permission)
            db.commit()
            db.refresh(permission)
            return permission

        except Exception as e:
            db.rollback()
            logger.exception("Error creating navigation permission")
            raise e

    @staticmethod
    def update(db: Session, permission_id: UUID, navigate_state: int) -> Optional[SysSecNavigationPermission]:
        """
        Update navigation state for a permission
        """
        try:
            permission = db.query(SysSecNavigationPermission).filter(
                SysSecNavigationPermission.Oid == permission_id
            ).first()

            if not permission:
                return None

            permission.NavigateState = navigate_state
            if permission.OptimisticLockField:
                permission.OptimisticLockField += 1
            else:
                permission.OptimisticLockField = 1

            db.commit()
            db.refresh(permission)
            return permission

        except Exception as e:
            db.rollback()
            logger.exception("Error updating navigation permission")
            raise e

    @staticmethod
    def fetch_by_role_and_path(db: Session, role_id: UUID, item_path: str) -> Optional[SysSecNavigationPermission]:
        """
        Fetch navigation permission by role and path
        """
        return db.query(SysSecNavigationPermission).filter(
            and_(
                SysSecNavigationPermission.Role == role_id,
                SysSecNavigationPermission.ItemPath == item_path
            )
        ).first()

    @staticmethod
    def fetch_by_role(db: Session, role_id: UUID) -> List[SysSecNavigationPermission]:
        """
        Fetch all navigation permissions for a role
        """
        return db.query(SysSecNavigationPermission).filter(
            SysSecNavigationPermission.Role == role_id
        ).order_by(SysSecNavigationPermission.ItemPath).all()

    @staticmethod
    def fetch_by_path(db: Session, item_path: str) -> List[SysSecNavigationPermission]:
        """
        Fetch all roles that have permission for a specific path
        """
        return db.query(SysSecNavigationPermission).options(
            joinedload(SysSecNavigationPermission.sys_sec_role)
        ).join(
            SysSecRole, SysSecNavigationPermission.Role == SysSecRole.Oid
        ).filter(
            and_(
                SysSecNavigationPermission.ItemPath == item_path,
                SysSecRole.GCRecord.is_(None)
            )
        ).order_by(SysSecRole.Name).all()

    @staticmethod
    def delete(db: Session, permission_id: UUID) -> bool:
        """
        Delete a navigation permission
        """
        try:
            permission = db.query(SysSecNavigationPermission).filter(
                SysSecNavigationPermission.Oid == permission_id
            ).first()

            if not permission:
                return False

            db.delete(permission)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting navigation permission")
            raise e

    @staticmethod
    def delete_by_role_and_path(db: Session, role_id: UUID, item_path: str) -> bool:
        """
        Delete navigation permission by role and path
        """
        try:
            permission = db.query(SysSecNavigationPermission).filter(
                and_(
                    SysSecNavigationPermission.Role == role_id,
                    SysSecNavigationPermission.ItemPath == item_path
                )
            ).first()

            if not permission:
                return False

            db.delete(permission)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting navigation permission")
            raise e

    @staticmethod
    def delete_all_for_role(db: Session, role_id: UUID) -> bool:
        """
        Delete all navigation permissions for a role
        """
        try:
            db.query(SysSecNavigationPermission).filter(
                SysSecNavigationPermission.Role == role_id
            ).delete()
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting role navigation permissions")
            raise e

    @staticmethod
    def bulk_create(db: Session, role_id: UUID, item_paths: List[str], navigate_state: int = 1) -> List[str]:
        """
        Create multiple navigation permissions for a role
        """
        try:
            # Get existing permissions to avoid duplicates
            existing_paths = {
                perm.ItemPath for perm in db.query(SysSecNavigationPermission).filter(
                    and_(
                        SysSecNavigationPermission.Role == role_id,
                        SysSecNavigationPermission.ItemPath.in_(item_paths)
                    )
                ).all()
            }

            # Filter out existing permissions
            new_paths = [path for path in item_paths if path not in existing_paths]

            if not new_paths:
                return []

            # Bulk insert
            new_permissions = [
                SysSecNavigationPermission(
                    Oid=uuid4(),
                    ItemPath=path,
                    NavigateState=navigate_state,
                    Role=role_id,
                    OptimisticLockField=0
                )
                for path in new_paths
            ]

            db.add_all(new_permissions)
            db.commit()
            return new_paths

        except Exception as e:
            db.rollback()
            logger.exception("Error in bulk create navigation permissions")
            raise e

    @staticmethod
    def fetch_all_paths(db: Session) -> List[str]:
        """
        Fetch all distinct navigation paths from the system
        """
        results = db.query(SysSecNavigationPermission.ItemPath).distinct().order_by(
            SysSecNavigationPermission.ItemPath
        ).all()
        return [row[0] for row in results]

    @staticmethod
    def count_permissions_for_role(db: Session, role_id: UUID) -> int:
        """
        Count navigation permissions for a role
        """
        return db.query(SysSecNavigationPermission).filter(
            SysSecNavigationPermission.Role == role_id
        ).count()

    @staticmethod
    def fetch_allowed_paths_for_role(db: Session, role_id: UUID) -> List[str]:
        """
        Fetch all allowed navigation paths for a role
        """
        results = db.query(SysSecNavigationPermission.ItemPath).filter(
            and_(
                SysSecNavigationPermission.Role == role_id,
                SysSecNavigationPermission.NavigateState == 1
            )
        ).order_by(SysSecNavigationPermission.ItemPath).all()
        return [row[0] for row in results]

    @staticmethod
    def fetch_denied_paths_for_role(db: Session, role_id: UUID) -> List[str]:
        """
        Fetch all denied navigation paths for a role
        """
        results = db.query(SysSecNavigationPermission.ItemPath).filter(
            and_(
                SysSecNavigationPermission.Role == role_id,
                SysSecNavigationPermission.NavigateState == 0
            )
        ).order_by(SysSecNavigationPermission.ItemPath).all()
        return [row[0] for row in results]
