"""
FastAPI Permission Dependencies for Casbin Authorization

This module provides FastAPI dependency functions for easy permission checking in endpoints.

Usage examples:

    # Check permission by resource type and action
    @router.get('/sessions/{session_id}')
    def get_session(
        session_id: UUID,
        current_user: dict = Depends(require_permission('msession', 'read'))
    ):
        return session

    # Check specific action permission
    @router.post('/admin/cleanup')
    def cleanup(_: dict = Depends(require_action('SystemMaintenance'))):
        return {"status": "cleaned"}

    # Check navigation permission
    @router.get('/settings')
    def settings(_: dict = Depends(require_navigation('/settings'))):
        return settings_data

    # Require specific role
    @router.get('/admin/users')
    def admin_users(_: dict = Depends(require_role('Administrator'))):
        return users

    # Get all user permissions
    @router.get('/me/permissions')
    def my_permissions(perms: dict = Depends(get_user_permissions)):
        return perms
"""
from typing import Callable, Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from services.casbin_service import CasbinService

import logging

logger = logging.getLogger(__name__)


# TODO: Replace with actual authentication dependency
# This is a placeholder - replace with your actual auth system
def get_current_user_id() -> Optional[UUID]:
    """
    Get the current authenticated user ID.

    IMPORTANT: This is a placeholder function. Replace this with your actual
    authentication dependency that extracts the user ID from JWT token or session.

    For now, it returns None, which will cause permission checks to fail.
    You should replace this with something like:

        from dependencies.auth import get_current_user

        def get_current_user_id(
            current_user: dict = Depends(get_current_user)
        ) -> UUID:
            return current_user['user_id']
    """
    logger.warning("Using placeholder get_current_user_id - implement actual authentication!")
    return None


def require_permission(resource_type: str, action: str) -> Callable:
    """
    Dependency factory for checking permissions on a resource type.

    Args:
        resource_type: The type of resource (e.g., 'msession', 'image', 'camera')
        action: The action to perform (e.g., 'read', 'write', 'delete', 'create')

    Returns:
        FastAPI dependency function that checks permission

    Raises:
        HTTPException: 401 if user not authenticated, 403 if permission denied

    Usage:
        @router.get('/sessions/{session_id}')
        def get_session(
            session_id: UUID,
            _: None = Depends(require_permission('msession', 'read'))
        ):
            # Permission already checked before this runs
            return get_session_data(session_id)
    """
    def permission_checker(
        user_id: Optional[UUID] = Depends(get_current_user_id)
    ) -> dict:
        # Check authentication
        if user_id is None:
            logger.warning(f"Unauthenticated access attempt to {resource_type}:{action}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Build resource identifier
        resource = f"{resource_type}:*"

        # Check permission using Casbin
        user_id_str = str(user_id)
        has_permission = CasbinService.enforce(user_id_str, resource, action)

        if not has_permission:
            logger.warning(
                f"Permission denied: user={user_id} tried to {action} on {resource_type}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Cannot {action} {resource_type}"
            )

        logger.debug(f"Permission granted: user={user_id} can {action} on {resource_type}")
        return {"user_id": user_id, "resource_type": resource_type, "action": action}

    return permission_checker


def require_permission_on_instance(
    resource_type: str,
    resource_id_param: str,
    action: str
) -> Callable:
    """
    Dependency factory for checking permissions on a specific resource instance.

    This is useful for object-level permissions where you want to check access
    to a specific resource like 'msession:123' instead of 'msession:*'.

    Args:
        resource_type: The type of resource (e.g., 'msession', 'image')
        resource_id_param: The path parameter name containing the resource ID
        action: The action to perform (e.g., 'read', 'write', 'delete')

    Returns:
        FastAPI dependency function that checks permission

    Usage:
        @router.get('/sessions/{session_id}')
        def get_session(
            session_id: UUID,
            _: None = Depends(require_permission_on_instance('msession', 'session_id', 'read'))
        ):
            return get_session_data(session_id)
    """
    def permission_checker(
        user_id: Optional[UUID] = Depends(get_current_user_id),
        **path_params
    ) -> dict:
        # Check authentication
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Extract resource ID from path parameters
        resource_id = path_params.get(resource_id_param)
        if resource_id is None:
            logger.error(f"Path parameter '{resource_id_param}' not found in request")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error: resource ID not found"
            )

        # Build resource identifier
        resource = f"{resource_type}:{resource_id}"

        # Check permission using Casbin
        user_id_str = str(user_id)
        has_permission = CasbinService.enforce(user_id_str, resource, action)

        if not has_permission:
            logger.warning(
                f"Permission denied: user={user_id} tried to {action} on {resource}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Cannot {action} {resource}"
            )

        logger.debug(f"Permission granted: user={user_id} can {action} on {resource}")
        return {"user_id": user_id, "resource": resource, "action": action}

    return permission_checker


def require_action(action_id: str) -> Callable:
    """
    Dependency factory for checking action permissions.

    Action permissions are system-wide actions that don't target a specific resource,
    like "SystemMaintenance", "ExportData", "ImportData", etc.

    Args:
        action_id: The action ID from sys_sec_action_permission table

    Returns:
        FastAPI dependency function that checks action permission

    Usage:
        @router.post('/admin/cleanup')
        def cleanup(_: None = Depends(require_action('SystemMaintenance'))):
            perform_cleanup()
            return {"status": "cleaned"}
    """
    def action_checker(
        user_id: Optional[UUID] = Depends(get_current_user_id)
    ) -> dict:
        # Check authentication
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Action permissions use "action:{ActionId}" format
        resource = f"action:{action_id}"

        # Check permission using Casbin
        user_id_str = str(user_id)
        has_permission = CasbinService.enforce(user_id_str, resource, "execute")

        if not has_permission:
            logger.warning(
                f"Action denied: user={user_id} tried to execute action={action_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Cannot execute action '{action_id}'"
            )

        logger.debug(f"Action granted: user={user_id} can execute action={action_id}")
        return {"user_id": user_id, "action_id": action_id}

    return action_checker


def require_navigation(item_path: str) -> Callable:
    """
    Dependency factory for checking navigation permissions.

    Navigation permissions control access to UI navigation items, menu items,
    or pages in the application.

    Args:
        item_path: The navigation item path (e.g., '/settings', '/admin/users')

    Returns:
        FastAPI dependency function that checks navigation permission

    Usage:
        @router.get('/settings')
        def settings(_: None = Depends(require_navigation('/settings'))):
            return settings_data
    """
    def navigation_checker(
        user_id: Optional[UUID] = Depends(get_current_user_id)
    ) -> dict:
        # Check authentication
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Navigation permissions use "navigation:{ItemPath}" format
        resource = f"navigation:{item_path}"

        # Check permission using Casbin
        user_id_str = str(user_id)
        has_permission = CasbinService.enforce(user_id_str, resource, "access")

        if not has_permission:
            logger.warning(
                f"Navigation denied: user={user_id} tried to access path={item_path}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Cannot access '{item_path}'"
            )

        logger.debug(f"Navigation granted: user={user_id} can access path={item_path}")
        return {"user_id": user_id, "item_path": item_path}

    return navigation_checker


def require_role(role_name: str) -> Callable:
    """
    Dependency factory for checking role membership.

    This checks if the user has a specific role assigned. Useful for endpoints
    that should only be accessible to users with a specific role.

    Args:
        role_name: The role name (e.g., 'Administrator', 'User', 'Guest')

    Returns:
        FastAPI dependency function that checks role membership

    Usage:
        @router.get('/admin/users')
        def admin_users(_: None = Depends(require_role('Administrator'))):
            return all_users
    """
    def role_checker(
        user_id: Optional[UUID] = Depends(get_current_user_id)
    ) -> dict:
        # Check authentication
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )

        # Check role membership using Casbin
        user_id_str = str(user_id)
        has_role = CasbinService.has_role_for_user(user_id_str, role_name)

        if not has_role:
            logger.warning(
                f"Role check failed: user={user_id} does not have role={role_name}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: Requires '{role_name}' role"
            )

        logger.debug(f"Role check passed: user={user_id} has role={role_name}")
        return {"user_id": user_id, "role_name": role_name}

    return role_checker


def get_user_permissions(
    user_id: Optional[UUID] = Depends(get_current_user_id)
) -> dict:
    """
    Dependency for getting all permissions for the current user.

    This is useful for endpoints that need to return information about
    what the user can and cannot do, like a "me" endpoint or a permissions
    summary page.

    Returns:
        Dictionary with user permissions, roles, and capabilities

    Usage:
        @router.get('/me/permissions')
        def my_permissions(perms: dict = Depends(get_user_permissions)):
            return perms
    """
    # Check authentication
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    user_id_str = str(user_id)

    # Get all roles for user
    roles = CasbinService.get_roles_for_user(user_id_str)

    # Get all implicit permissions (includes inherited from roles)
    implicit_permissions = CasbinService.get_implicit_permissions_for_user(user_id_str)

    # Get direct permissions (without role inheritance)
    direct_permissions = CasbinService.get_permissions_for_user(user_id_str)

    # Check if user is admin
    is_admin = "Administrator" in roles

    return {
        "user_id": user_id,
        "roles": roles,
        "is_admin": is_admin,
        "direct_permissions": direct_permissions,
        "implicit_permissions": implicit_permissions,
        "total_permissions": len(implicit_permissions)
    }


def check_permission(
    user_id: UUID,
    resource: str,
    action: str
) -> bool:
    """
    Utility function to check permission programmatically (not a dependency).

    Use this when you need to check permissions in service/repository layers
    or when you need conditional logic based on permissions.

    Args:
        user_id: The user ID to check
        resource: The resource to check (e.g., 'msession:123', 'msession:*')
        action: The action to check (e.g., 'read', 'write', 'delete')

    Returns:
        True if user has permission, False otherwise

    Usage:
        # In a service method
        if check_permission(user_id, 'msession:123', 'delete'):
            delete_session(session_id)
        else:
            raise PermissionError()
    """
    user_id_str = str(user_id)
    return CasbinService.enforce(user_id_str, resource, action)


def filter_by_permissions(
    user_id: UUID,
    resource_type: str,
    action: str,
    db: Session
) -> dict:
    """
    Utility function to get filtering criteria based on user permissions.

    This is used for list endpoints where we need to filter query results
    based on what the user can access. For now, it returns simple allow/deny.

    In future iterations, this will parse object-level permissions with criteria
    like "owner_id = CurrentUserId()" to build SQLAlchemy filters.

    Args:
        user_id: The user ID to check
        resource_type: The resource type (e.g., 'msession', 'image')
        action: The action (e.g., 'read', 'list')
        db: Database session for querying permissions

    Returns:
        Dictionary with filtering information:
        {
            "allowed": bool,           # Can user access this resource type at all?
            "filter_all": bool,        # Should we filter to only user's own records?
            "criteria": Optional[str]  # Future: parsed criteria for filtering
        }

    Usage:
        # In a list endpoint
        filter_info = filter_by_permissions(user_id, 'msession', 'read', db)
        if not filter_info['allowed']:
            return []  # User can't see any sessions

        query = db.query(MSession)
        if filter_info['filter_all']:
            query = query.filter(MSession.owner_id == user_id)

        return query.all()
    """
    user_id_str = str(user_id)
    resource = f"{resource_type}:*"

    # Check if user has wildcard permission
    has_wildcard = CasbinService.enforce(user_id_str, resource, action)

    # Check if user is admin
    is_admin = CasbinService.has_role_for_user(user_id_str, "Administrator")

    if is_admin:
        # Admin can see everything
        return {
            "allowed": True,
            "filter_all": False,
            "criteria": None
        }

    if has_wildcard:
        # User has wildcard permission - can see everything
        return {
            "allowed": True,
            "filter_all": False,
            "criteria": None
        }

    # TODO: Phase 2 - Check object-level permissions
    # This would query sys_sec_object_permission for criteria like:
    # - "owner_id = CurrentUserId()"
    # - "department_id IN (SELECT department_id FROM user_departments WHERE user_id = CurrentUserId())"
    # And parse them into SQLAlchemy filters

    # For now, if no wildcard permission, assume no access
    return {
        "allowed": False,
        "filter_all": True,
        "criteria": None
    }


# Export all public functions
__all__ = [
    'require_permission',
    'require_permission_on_instance',
    'require_action',
    'require_navigation',
    'require_role',
    'get_user_permissions',
    'check_permission',
    'filter_by_permissions',
]
