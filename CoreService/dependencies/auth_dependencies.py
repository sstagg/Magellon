"""
Authorization dependencies and decorators for FastAPI endpoints
"""
from typing import List, Optional
from uuid import UUID
from functools import wraps

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from services.authorization_service import AuthorizationService

import logging

logger = logging.getLogger(__name__)


# ==================== DEPENDENCY FUNCTIONS ====================

def get_current_user_id() -> Optional[UUID]:
    """
    Get current user ID from session/JWT token
    
    In a real implementation, this should:
    1. Extract the JWT token from the request headers
    2. Validate and decode the token
    3. Return the user ID from the token claims
    
    For now, this is a placeholder that returns None.
    You should implement this based on your authentication mechanism.
    """
    # TODO: Implement actual JWT token extraction and validation
    # Example:
    # token = request.headers.get("Authorization")
    # payload = decode_jwt(token)
    # return UUID(payload["user_id"])
    
    return None


async def require_authenticated_user(
    current_user_id: Optional[UUID] = Depends(get_current_user_id)
) -> UUID:
    """
    Dependency that requires an authenticated user
    Raises 401 if user is not authenticated
    """
    if current_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return current_user_id


async def require_admin_user(
    current_user_id: UUID = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
) -> UUID:
    """
    Dependency that requires an admin user
    Raises 403 if user is not an administrator
    """
    if not AuthorizationService.user_is_admin(db, current_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required"
        )
    return current_user_id


def require_role(required_role: str):
    """
    Dependency factory that requires a specific role
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(
            user_id: UUID = Depends(require_role("Administrator"))
        ):
            return {"message": "Admin access granted"}
    """
    async def role_checker(
        current_user_id: UUID = Depends(require_authenticated_user),
        db: Session = Depends(get_db)
    ) -> UUID:
        if not AuthorizationService.user_has_role(db, current_user_id, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' is required"
            )
        return current_user_id
    
    return role_checker


def require_any_role(required_roles: List[str]):
    """
    Dependency factory that requires any of the specified roles
    
    Usage:
        @router.get("/manager-or-admin")
        async def endpoint(
            user_id: UUID = Depends(require_any_role(["Manager", "Administrator"]))
        ):
            return {"message": "Access granted"}
    """
    async def any_role_checker(
        current_user_id: UUID = Depends(require_authenticated_user),
        db: Session = Depends(get_db)
    ) -> UUID:
        if not AuthorizationService.user_has_any_role(db, current_user_id, required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of the following roles is required: {', '.join(required_roles)}"
            )
        return current_user_id
    
    return any_role_checker


def require_all_roles(required_roles: List[str]):
    """
    Dependency factory that requires all of the specified roles
    
    Usage:
        @router.get("/multi-role")
        async def endpoint(
            user_id: UUID = Depends(require_all_roles(["Manager", "Auditor"]))
        ):
            return {"message": "Access granted"}
    """
    async def all_roles_checker(
        current_user_id: UUID = Depends(require_authenticated_user),
        db: Session = Depends(get_db)
    ) -> UUID:
        if not AuthorizationService.user_has_all_roles(db, current_user_id, required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"All of the following roles are required: {', '.join(required_roles)}"
            )
        return current_user_id
    
    return all_roles_checker


def require_action_permission(action_id: str):
    """
    Dependency factory that requires a specific action permission
    
    Usage:
        @router.post("/create-invoice")
        async def create_invoice(
            user_id: UUID = Depends(require_action_permission("CreateInvoice"))
        ):
            return {"message": "Invoice created"}
    """
    async def action_permission_checker(
        current_user_id: UUID = Depends(require_authenticated_user),
        db: Session = Depends(get_db)
    ) -> UUID:
        if not AuthorizationService.user_has_action_permission(db, current_user_id, action_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission for action '{action_id}' is required"
            )
        return current_user_id
    
    return action_permission_checker


def require_navigation_permission(item_path: str):
    """
    Dependency factory that requires navigation permission to a path
    
    Usage:
        @router.get("/admin/settings")
        async def get_settings(
            user_id: UUID = Depends(require_navigation_permission("/admin/settings"))
        ):
            return {"settings": {}}
    """
    async def navigation_permission_checker(
        current_user_id: UUID = Depends(require_authenticated_user),
        db: Session = Depends(get_db)
    ) -> UUID:
        if not AuthorizationService.user_has_navigation_permission(db, current_user_id, item_path):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission to navigate to '{item_path}' is required"
            )
        return current_user_id
    
    return navigation_permission_checker


def require_type_permission(target_type: str, operation: str = 'read'):
    """
    Dependency factory that requires type permission for a specific operation
    
    Usage:
        @router.get("/properties")
        async def get_properties(
            user_id: UUID = Depends(require_type_permission("Property", "read"))
        ):
            return {"properties": []}
    """
    async def type_permission_checker(
        current_user_id: UUID = Depends(require_authenticated_user),
        db: Session = Depends(get_db)
    ) -> UUID:
        if not AuthorizationService.user_has_type_permission(db, current_user_id, target_type, operation):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission for '{operation}' on type '{target_type}' is required"
            )
        return current_user_id
    
    return type_permission_checker


# ==================== MANUAL PERMISSION CHECK FUNCTIONS ====================

async def check_user_permission(
    user_id: UUID,
    permission_type: str,
    resource: str,
    operation: Optional[str] = None,
    db: Session = Depends(get_db)
) -> bool:
    """
    Manually check if a user has a specific permission
    
    Args:
        user_id: User ID to check
        permission_type: Type of permission ('action', 'navigation', 'type', 'role')
        resource: Resource identifier (action_id, path, type_name, or role_name)
        operation: Operation type for type permissions ('read', 'write', 'create', 'delete')
        db: Database session
    
    Returns:
        True if user has permission, False otherwise
    """
    has_permission, _ = AuthorizationService.check_permission(
        db, user_id, permission_type, resource, operation
    )
    return has_permission


async def assert_user_permission(
    user_id: UUID,
    permission_type: str,
    resource: str,
    operation: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Assert that a user has a specific permission, raise HTTPException if not
    
    Args:
        user_id: User ID to check
        permission_type: Type of permission ('action', 'navigation', 'type', 'role')
        resource: Resource identifier
        operation: Operation type for type permissions
        db: Database session
    
    Raises:
        HTTPException: If user lacks the required permission
    """
    has_permission, reason = AuthorizationService.check_permission(
        db, user_id, permission_type, resource, operation
    )
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason or "Permission denied"
        )


# ==================== DECORATOR FOR FUNCTION-LEVEL AUTHORIZATION ====================

def authorize_role(required_role: str):
    """
    Decorator for function-level role authorization
    
    Usage:
        @authorize_role("Administrator")
        async def some_function(user_id: UUID, db: Session):
            # Function logic
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_id and db from kwargs or args
            user_id = kwargs.get('user_id') or kwargs.get('current_user_id')
            db = kwargs.get('db')
            
            if user_id is None or db is None:
                raise ValueError("user_id and db must be provided to the decorated function")
            
            if not AuthorizationService.user_has_role(db, user_id, required_role):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{required_role}' is required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def authorize_action(action_id: str):
    """
    Decorator for function-level action permission authorization
    
    Usage:
        @authorize_action("DeleteUser")
        async def delete_user(user_id: UUID, target_user_id: UUID, db: Session):
            # Function logic
            pass
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user_id = kwargs.get('user_id') or kwargs.get('current_user_id')
            db = kwargs.get('db')
            
            if user_id is None or db is None:
                raise ValueError("user_id and db must be provided to the decorated function")
            
            if not AuthorizationService.user_has_action_permission(db, user_id, action_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission for action '{action_id}' is required"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# ==================== EXAMPLE USAGE ====================

"""
Example usage in your FastAPI routes:

from fastapi import APIRouter, Depends
from uuid import UUID
from sqlalchemy.orm import Session
from .dependencies.auth_dependencies import (
    require_authenticated_user,
    require_admin_user,
    require_role,
    require_any_role,
    require_action_permission,
    require_navigation_permission,
    require_type_permission
)
from database import get_db

router = APIRouter()

# Require authenticated user
@router.get("/profile")
async def get_profile(
    user_id: UUID = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    return {"user_id": str(user_id)}

# Require admin user
@router.get("/admin/dashboard")
async def admin_dashboard(
    user_id: UUID = Depends(require_admin_user)
):
    return {"message": "Admin dashboard"}

# Require specific role
@router.get("/manager/reports")
async def manager_reports(
    user_id: UUID = Depends(require_role("Manager"))
):
    return {"reports": []}

# Require any of multiple roles
@router.get("/supervisor-area")
async def supervisor_area(
    user_id: UUID = Depends(require_any_role(["Manager", "Supervisor", "Administrator"]))
):
    return {"data": "supervisor data"}

# Require specific action permission
@router.post("/create-invoice")
async def create_invoice(
    user_id: UUID = Depends(require_action_permission("CreateInvoice"))
):
    return {"message": "Invoice created"}

# Require navigation permission
@router.get("/admin/settings")
async def admin_settings(
    user_id: UUID = Depends(require_navigation_permission("/admin/settings"))
):
    return {"settings": {}}

# Require type permission
@router.get("/properties")
async def get_properties(
    user_id: UUID = Depends(require_type_permission("Property", "read"))
):
    return {"properties": []}

@router.post("/properties")
async def create_property(
    user_id: UUID = Depends(require_type_permission("Property", "create"))
):
    return {"message": "Property created"}
"""
