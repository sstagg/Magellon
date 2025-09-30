"""
Controller for Permission Checking API endpoints
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from models.security.security_models import (
    PermissionCheckRequest,
    PermissionCheckResponse,
    UserPermissionsSummaryDto
)
from services.authorization_service import AuthorizationService
from repositories.security.sys_sec_user_repository import SysSecUserRepository

import logging

logger = logging.getLogger(__name__)

sys_sec_permission_router = APIRouter()


@sys_sec_permission_router.post('/check', response_model=PermissionCheckResponse)
async def check_permission(
        permission_request: PermissionCheckRequest,
        db: Session = Depends(get_db)
):
    """
    Check if a user has a specific permission
    """
    try:
        # Validate user exists
        user = SysSecUserRepository.fetch_by_id(db, permission_request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        has_permission, reason = AuthorizationService.check_permission(
            db=db,
            user_id=permission_request.user_id,
            permission_type=permission_request.permission_type,
            resource=permission_request.resource,
            operation=permission_request.operation
        )

        return PermissionCheckResponse(
            has_permission=has_permission,
            reason=reason
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error checking permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking permission'
        )


@sys_sec_permission_router.get('/user/{user_id}/summary', response_model=UserPermissionsSummaryDto)
async def get_user_permissions_summary(
        user_id: UUID,
        db: Session = Depends(get_db)
):
    """
    Get comprehensive summary of all user permissions
    """
    try:
        # Validate user exists
        user = SysSecUserRepository.fetch_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        summary = AuthorizationService.get_user_permissions_summary(db, user_id)
        
        # Convert to response DTO
        from models.security_models import RoleResponseDto, ActionPermissionResponseDto, NavigationPermissionResponseDto
        
        return {
            "user_id": user_id,
            "username": user.USERNAME,
            "roles": [
                RoleResponseDto(
                    oid=UUID(role['role_id']),
                    name=role['role_name'],
                    is_administrative=role['is_administrative'],
                    can_edit_model=False,  # Not available in summary
                    permission_policy=0,  # Not available in summary
                    tenant_id=None
                )
                for role in summary['roles']
            ],
            "action_permissions": [
                ActionPermissionResponseDto(
                    oid=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
                    action_id=action_id,
                    role_id=UUID('00000000-0000-0000-0000-000000000000')  # Placeholder
                )
                for action_id in summary['action_permissions']
            ],
            "navigation_permissions": [
                NavigationPermissionResponseDto(
                    oid=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
                    item_path=nav_perm['path'],
                    navigate_state=1 if nav_perm['allowed'] else 0,
                    role_id=UUID('00000000-0000-0000-0000-000000000000')  # Placeholder
                )
                for nav_perm in summary['navigation_permissions']
            ],
            "is_admin": summary['is_admin']
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error getting user permissions summary')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error getting user permissions summary'
        )


@sys_sec_permission_router.get('/user/{user_id}/has-role/{role_name}')
async def check_user_has_role(
        user_id: UUID,
        role_name: str,
        db: Session = Depends(get_db)
):
    """
    Check if a user has a specific role
    """
    try:
        has_role = AuthorizationService.user_has_role(db, user_id, role_name)
        return {
            "user_id": str(user_id),
            "role_name": role_name,
            "has_role": has_role
        }

    except Exception as e:
        logger.exception('Error checking user role')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking user role'
        )


@sys_sec_permission_router.get('/user/{user_id}/is-admin')
async def check_user_is_admin(
        user_id: UUID,
        db: Session = Depends(get_db)
):
    """
    Check if a user has any administrative role
    """
    try:
        is_admin = AuthorizationService.user_is_admin(db, user_id)
        return {
            "user_id": str(user_id),
            "is_admin": is_admin
        }

    except Exception as e:
        logger.exception('Error checking admin status')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking admin status'
        )


@sys_sec_permission_router.get('/user/{user_id}/action/{action_id}')
async def check_action_permission(
        user_id: UUID,
        action_id: str,
        db: Session = Depends(get_db)
):
    """
    Check if a user has a specific action permission
    """
    try:
        has_permission = AuthorizationService.user_has_action_permission(db, user_id, action_id)
        return {
            "user_id": str(user_id),
            "action_id": action_id,
            "has_permission": has_permission
        }

    except Exception as e:
        logger.exception('Error checking action permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking action permission'
        )


@sys_sec_permission_router.get('/user/{user_id}/navigation')
async def check_navigation_permission(
        user_id: UUID,
        item_path: str = Query(..., description="Navigation path to check"),
        db: Session = Depends(get_db)
):
    """
    Check if a user has permission to navigate to a specific path
    """
    try:
        has_permission = AuthorizationService.user_has_navigation_permission(db, user_id, item_path)
        return {
            "user_id": str(user_id),
            "item_path": item_path,
            "has_permission": has_permission
        }

    except Exception as e:
        logger.exception('Error checking navigation permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking navigation permission'
        )


@sys_sec_permission_router.get('/user/{user_id}/type/{target_type}')
async def check_type_permission(
        user_id: UUID,
        target_type: str,
        operation: str = Query('read', description="Operation: read, write, create, delete, navigate"),
        db: Session = Depends(get_db)
):
    """
    Check if a user has permission for a specific type/operation
    """
    try:
        if operation not in ['read', 'write', 'create', 'delete', 'navigate']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid operation. Must be one of: read, write, create, delete, navigate"
            )

        has_permission = AuthorizationService.user_has_type_permission(
            db, user_id, target_type, operation
        )
        
        return {
            "user_id": str(user_id),
            "target_type": target_type,
            "operation": operation,
            "has_permission": has_permission
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error checking type permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking type permission'
        )


@sys_sec_permission_router.get('/user/{user_id}/roles')
async def get_user_roles(
        user_id: UUID,
        db: Session = Depends(get_db)
):
    """
    Get all roles for a user
    """
    try:
        roles = AuthorizationService.get_user_roles(db, user_id)
        return {
            "user_id": str(user_id),
            "roles": [
                {
                    "role_id": str(role['role_id']),
                    "role_name": role['role_name'],
                    "is_administrative": role['is_administrative'],
                    "can_edit_model": role['can_edit_model']
                }
                for role in roles
            ]
        }

    except Exception as e:
        logger.exception('Error getting user roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error getting user roles'
        )
