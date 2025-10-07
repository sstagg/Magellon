"""
FastAPI Dependencies Package

This package contains reusable FastAPI dependency functions for:
- Permission checking (Casbin-based authorization)
- Authentication (TODO: implement)
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
