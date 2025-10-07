"""
FastAPI Dependencies Package

This package contains reusable FastAPI dependency functions for:
- Permission checking (Casbin-based authorization)
- Authentication (JWT-based)
- Rate limiting (TODO: implement)
- Request validation (TODO: implement)
"""

from dependencies.permissions import (
    require_permission,
    require_permission_on_instance,
    require_action,
    require_navigation,
    require_role,
    get_user_permissions,
    check_permission,
    filter_by_permissions,
)

from dependencies.auth import (
    get_current_user_id,
    get_current_user,
    get_optional_current_user_id,
    create_access_token,
)

__all__ = [
    # Permission dependencies
    'require_permission',
    'require_permission_on_instance',
    'require_action',
    'require_navigation',
    'require_role',
    'get_user_permissions',
    'check_permission',
    'filter_by_permissions',
    # Authentication dependencies
    'get_current_user_id',
    'get_current_user',
    'get_optional_current_user_id',
    'create_access_token',
]
