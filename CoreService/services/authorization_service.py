"""
Authorization Service for checking user permissions
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy.orm import Session

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
            return SysSecUserRoleRepository.fetch_roles_by_user(db, user_id)
        except Exception as e:
            logger.exception(f"Error fetching user roles: {e}")
            return []

    @staticmethod
    def user_has_action_permission(db: Session, user_id: UUID, action_id: str) -> bool:
        """
        Check if a user has permission for a specific action
        """
        try:
            from sqlalchemy import text
            
            # Check if user has any role that grants this action permission
            query = text("""
                SELECT COUNT(*)
                FROM sys_sec_user_role ur
                JOIN sys_sec_action_permission ap ON ur."Roles" = ap."Role"
                JOIN sys_sec_role r ON ur."Roles" = r."Oid"
                WHERE ur."People" = :user_id 
                    AND ap."ActionId" = :action_id
                    AND r."GCRecord" IS NULL
            """)

            result = db.execute(query, {
                "user_id": user_id,
                "action_id": action_id
            })
            count = result.scalar()
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
            from sqlalchemy import text
            
            # Check if user has any role that grants this navigation permission
            # NavigateState: 1 = Allow, 0 = Deny
            query = text("""
                SELECT MAX(np."NavigateState")
                FROM sys_sec_user_role ur
                JOIN sys_sec_navigation_permission np ON ur."Roles" = np."Role"
                JOIN sys_sec_role r ON ur."Roles" = r."Oid"
                WHERE ur."People" = :user_id 
                    AND np."ItemPath" = :item_path
                    AND r."GCRecord" IS NULL
            """)

            result = db.execute(query, {
                "user_id": user_id,
                "item_path": item_path
            })
            state = result.scalar()
            
            # If no specific permission found, check if user is admin
            if state is None:
                return AuthorizationService.user_is_admin(db, user_id)
            
            return state == 1

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
            from sqlalchemy import text
            
            # Map operation to column name
            operation_column_map = {
                'read': 'ReadState',
                'write': 'WriteState',
                'create': 'CreateState',
                'delete': 'DeleteState',
                'navigate': 'NavigateState'
            }
            
            if operation not in operation_column_map:
                logger.warning(f"Invalid operation: {operation}")
                return False
                
            column_name = operation_column_map[operation]
            
            # Check if user has any role that grants this type permission
            query = text(f"""
                SELECT MAX(tp."{column_name}")
                FROM sys_sec_user_role ur
                JOIN sys_sec_type_permission tp ON ur."Roles" = tp."Role"
                JOIN sys_sec_role r ON ur."Roles" = r."Oid"
                WHERE ur."People" = :user_id 
                    AND tp."TargetType" = :target_type
                    AND r."GCRecord" IS NULL
            """)

            result = db.execute(query, {
                "user_id": user_id,
                "target_type": target_type
            })
            state = result.scalar()
            
            # If no specific permission found, check if user is admin
            if state is None:
                return AuthorizationService.user_is_admin(db, user_id)
            
            return state == 1

        except Exception as e:
            logger.exception(f"Error checking type permission: {e}")
            return False

    @staticmethod
    def get_user_permissions_summary(db: Session, user_id: UUID) -> dict:
        """
        Get a comprehensive summary of user's permissions
        """
        try:
            from sqlalchemy import text
            
            # Get all roles
            roles = AuthorizationService.get_user_roles(db, user_id)
            
            # Get all action permissions
            action_query = text("""
                SELECT DISTINCT ap."ActionId"
                FROM sys_sec_user_role ur
                JOIN sys_sec_action_permission ap ON ur."Roles" = ap."Role"
                JOIN sys_sec_role r ON ur."Roles" = r."Oid"
                WHERE ur."People" = :user_id AND r."GCRecord" IS NULL
                ORDER BY ap."ActionId"
            """)
            action_result = db.execute(action_query, {"user_id": user_id})
            action_permissions = [row[0] for row in action_result.fetchall()]
            
            # Get all navigation permissions
            nav_query = text("""
                SELECT DISTINCT np."ItemPath", np."NavigateState"
                FROM sys_sec_user_role ur
                JOIN sys_sec_navigation_permission np ON ur."Roles" = np."Role"
                JOIN sys_sec_role r ON ur."Roles" = r."Oid"
                WHERE ur."People" = :user_id AND r."GCRecord" IS NULL
                ORDER BY np."ItemPath"
            """)
            nav_result = db.execute(nav_query, {"user_id": user_id})
            navigation_permissions = [
                {"path": row[0], "allowed": row[1] == 1} 
                for row in nav_result.fetchall()
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
