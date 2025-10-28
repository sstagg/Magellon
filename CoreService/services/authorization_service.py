"""
Authorization Service for checking user permissions
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session, joinedload

from models.sqlalchemy_models import (
    SysSecUserRole,
    SysSecRole,
    SysSecActionPermission,
    SysSecNavigationPermission,
    SysSecTypePermission
)
from repositories.security.sys_sec_user_role_repository import SysSecUserRoleRepository

import logging

logger = logging.getLogger(__name__)


class AuthorizationService:
    """Service for handling authorization and permission checks"""

    @staticmethod
    def user_has_role(db: Session, user_id: UUID, role_name: str) -> bool:
        """
        Check if a user has a specific role
        """
        try:
            return SysSecUserRoleRepository.user_has_role(db, user_id, role_name)
        except Exception as e:
            logger.exception(f"Error checking if user has role: {e}")
            return False

    @staticmethod
    def user_has_any_role(db: Session, user_id: UUID, role_names: List[str]) -> bool:
        """
        Check if a user has any of the specified roles
        """
        try:
            for role_name in role_names:
                if SysSecUserRoleRepository.user_has_role(db, user_id, role_name):
                    return True
            return False
        except Exception as e:
            logger.exception(f"Error checking if user has any role: {e}")
            return False

    @staticmethod
    def user_has_all_roles(db: Session, user_id: UUID, role_names: List[str]) -> bool:
        """
        Check if a user has all of the specified roles
        """
        try:
            for role_name in role_names:
                if not SysSecUserRoleRepository.user_has_role(db, user_id, role_name):
                    return False
            return True
        except Exception as e:
            logger.exception(f"Error checking if user has all roles: {e}")
            return False

    @staticmethod
    def user_is_admin(db: Session, user_id: UUID) -> bool:
        """
        Check if a user has any administrative role
        """
        try:
            return SysSecUserRoleRepository.user_has_any_administrative_role(db, user_id)
        except Exception as e:
            logger.exception(f"Error checking if user is admin: {e}")
            return False

    @staticmethod
    def get_user_roles(db: Session, user_id: UUID) -> List[dict]:
        """
        Get all roles for a user
        """
        try:
            # Use repository method which already has joinedload for sys_sec_role
            user_roles = SysSecUserRoleRepository.fetch_roles_by_user(db, user_id)

            # Access role attributes - already loaded via joinedload
            return [
                {
                    "role_id": ur.Roles,
                    "role_name": ur.sys_sec_role.Name if ur.sys_sec_role else None,
                    "is_administrative": ur.sys_sec_role.IsAdministrative if ur.sys_sec_role else False,
                    "can_edit_model": ur.sys_sec_role.CanEditModel if ur.sys_sec_role else False
                }
                for ur in user_roles
                if ur.sys_sec_role is not None
            ]
        except Exception as e:
            logger.exception(f"Error fetching user roles: {e}")
            return []

    @staticmethod
    def user_has_action_permission(db: Session, user_id: UUID, action_id: str) -> bool:
        """
        Check if a user has permission for a specific action
        """
        try:
            # Check if user has any role that grants this action permission using ORM
            count = db.query(SysSecActionPermission).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecActionPermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecActionPermission.ActionId == action_id,
                    SysSecRole.GCRecord.is_(None)
                )
            ).count()

            return count > 0

        except Exception as e:
            logger.exception(f"Error checking action permission: {e}")
            return False

    @staticmethod
    def user_has_navigation_permission(db: Session, user_id: UUID, item_path: str) -> bool:
        """
        Check if a user has permission to navigate to a specific path
        """
        try:
            # Check if user has any role that grants this navigation permission
            # NavigateState: 1 = Allow, 0 = Deny
            # Get the maximum navigate state (if any role allows it, allow)
            max_state = db.query(
                func.max(SysSecNavigationPermission.NavigateState)
            ).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecNavigationPermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecNavigationPermission.ItemPath == item_path,
                    SysSecRole.GCRecord.is_(None)
                )
            ).scalar()

            # If no specific permission found, check if user is admin
            if max_state is None:
                return AuthorizationService.user_is_admin(db, user_id)

            return max_state == 1

        except Exception as e:
            logger.exception(f"Error checking navigation permission: {e}")
            return False

    @staticmethod
    def user_has_type_permission(
        db: Session,
        user_id: UUID,
        target_type: str,
        operation: str = 'read'
    ) -> bool:
        """
        Check if a user has permission for a specific type/class
        operation: 'read', 'write', 'create', 'delete', 'navigate'
        """
        try:
            # Map operation to column attribute
            operation_column_map = {
                'read': SysSecTypePermission.ReadState,
                'write': SysSecTypePermission.WriteState,
                'create': SysSecTypePermission.CreateState,
                'delete': SysSecTypePermission.DeleteState,
                'navigate': SysSecTypePermission.NavigateState
            }

            if operation not in operation_column_map:
                logger.warning(f"Invalid operation: {operation}")
                return False

            column_attr = operation_column_map[operation]

            # Check if user has any role that grants this type permission
            # Get the maximum state (if any role allows it, allow)
            max_state = db.query(
                func.max(column_attr)
            ).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecTypePermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecTypePermission.TargetType == target_type,
                    SysSecRole.GCRecord.is_(None)
                )
            ).scalar()

            # If no specific permission found, check if user is admin
            if max_state is None:
                return AuthorizationService.user_is_admin(db, user_id)

            return max_state == 1

        except Exception as e:
            logger.exception(f"Error checking type permission: {e}")
            return False

    @staticmethod
    def get_user_permissions_summary(db: Session, user_id: UUID) -> dict:
        """
        Get a comprehensive summary of user's permissions
        """
        try:
            # Get all roles
            roles = AuthorizationService.get_user_roles(db, user_id)

            # Get all action permissions using ORM
            action_permissions_query = db.query(
                SysSecActionPermission.ActionId
            ).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecActionPermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecRole.GCRecord.is_(None)
                )
            ).distinct().order_by(SysSecActionPermission.ActionId)

            action_permissions = [row[0] for row in action_permissions_query.all()]

            # Get all navigation permissions using ORM
            nav_permissions_query = db.query(
                SysSecNavigationPermission.ItemPath,
                SysSecNavigationPermission.NavigateState
            ).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecNavigationPermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecRole.GCRecord.is_(None)
                )
            ).distinct().order_by(SysSecNavigationPermission.ItemPath)

            navigation_permissions = [
                {"path": row[0], "allowed": row[1] == 1}
                for row in nav_permissions_query.all()
            ]

            # Check if admin
            is_admin = AuthorizationService.user_is_admin(db, user_id)

            return {
                "user_id": str(user_id),
                "is_admin": is_admin,
                "roles": [
                    {
                        "role_id": str(role['role_id']),
                        "role_name": role['role_name'],
                        "is_administrative": role['is_administrative']
                    }
                    for role in roles
                ],
                "action_permissions": action_permissions,
                "navigation_permissions": navigation_permissions
            }

        except Exception as e:
            logger.exception(f"Error getting user permissions summary: {e}")
            return {
                "user_id": str(user_id),
                "is_admin": False,
                "roles": [],
                "action_permissions": [],
                "navigation_permissions": [],
                "error": str(e)
            }

    @staticmethod
    def get_user_action_permissions(db: Session, user_id: UUID) -> List[str]:
        """
        Get all action permissions for a user
        """
        try:
            action_permissions = db.query(
                SysSecActionPermission.ActionId
            ).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecActionPermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecRole.GCRecord.is_(None)
                )
            ).distinct().order_by(SysSecActionPermission.ActionId).all()

            return [row[0] for row in action_permissions]

        except Exception as e:
            logger.exception(f"Error getting user action permissions: {e}")
            return []

    @staticmethod
    def get_user_navigation_permissions(db: Session, user_id: UUID) -> List[dict]:
        """
        Get all navigation permissions for a user
        """
        try:
            nav_permissions = db.query(
                SysSecNavigationPermission.ItemPath,
                SysSecNavigationPermission.NavigateState
            ).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecNavigationPermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecRole.GCRecord.is_(None)
                )
            ).distinct().order_by(SysSecNavigationPermission.ItemPath).all()

            return [
                {"path": row[0], "allowed": row[1] == 1}
                for row in nav_permissions
            ]

        except Exception as e:
            logger.exception(f"Error getting user navigation permissions: {e}")
            return []

    @staticmethod
    def get_user_type_permissions(db: Session, user_id: UUID) -> List[dict]:
        """
        Get all type permissions for a user
        """
        try:
            type_permissions = db.query(
                SysSecTypePermission.TargetType,
                SysSecTypePermission.ReadState,
                SysSecTypePermission.WriteState,
                SysSecTypePermission.CreateState,
                SysSecTypePermission.DeleteState,
                SysSecTypePermission.NavigateState
            ).join(
                SysSecUserRole, SysSecUserRole.Roles == SysSecTypePermission.Role
            ).join(
                SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
            ).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecRole.GCRecord.is_(None)
                )
            ).distinct().order_by(SysSecTypePermission.TargetType).all()

            return [
                {
                    "type": row[0],
                    "read": row[1] == 1,
                    "write": row[2] == 1,
                    "create": row[3] == 1,
                    "delete": row[4] == 1,
                    "navigate": row[5] == 1
                }
                for row in type_permissions
            ]

        except Exception as e:
            logger.exception(f"Error getting user type permissions: {e}")
            return []

    @staticmethod
    def check_permission(
        db: Session,
        user_id: UUID,
        permission_type: str,
        resource: str,
        operation: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Generic permission check method
        Returns: (has_permission: bool, reason: Optional[str])
        """
        try:
            # Admin users have all permissions
            if AuthorizationService.user_is_admin(db, user_id):
                return True, "User has administrative privileges"

            if permission_type == 'action':
                has_perm = AuthorizationService.user_has_action_permission(db, user_id, resource)
                reason = None if has_perm else f"User lacks permission for action: {resource}"
                return has_perm, reason

            elif permission_type == 'navigation':
                has_perm = AuthorizationService.user_has_navigation_permission(db, user_id, resource)
                reason = None if has_perm else f"User lacks permission to navigate to: {resource}"
                return has_perm, reason

            elif permission_type == 'type':
                if not operation:
                    operation = 'read'
                has_perm = AuthorizationService.user_has_type_permission(db, user_id, resource, operation)
                reason = None if has_perm else f"User lacks {operation} permission for type: {resource}"
                return has_perm, reason

            elif permission_type == 'role':
                has_perm = AuthorizationService.user_has_role(db, user_id, resource)
                reason = None if has_perm else f"User does not have role: {resource}"
                return has_perm, reason

            else:
                return False, f"Unknown permission type: {permission_type}"

        except Exception as e:
            logger.exception(f"Error checking permission: {e}")
            return False, f"Error checking permission: {str(e)}"
