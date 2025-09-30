"""
Controller for Permission Management API endpoints (Action, Navigation, Type)
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from models.security.security_models import (
    ActionPermissionCreateDto,
    ActionPermissionResponseDto,
    NavigationPermissionCreateDto,
    NavigationPermissionResponseDto,
    TypePermissionCreateDto,
    TypePermissionResponseDto,
    BulkPermissionCreateDto,
    PermissionBatchResponseDto
)
from repositories.security.sys_sec_action_permission_repository import SysSecActionPermissionRepository
from repositories.security.sys_sec_navigation_permission_repository import SysSecNavigationPermissionRepository
from repositories.security.sys_sec_type_permission_repository import SysSecTypePermissionRepository
from repositories.security.sys_sec_role_repository import SysSecRoleRepository

import logging

logger = logging.getLogger(__name__)

sys_sec_permission_mgmt_router = APIRouter()


# ==================== ACTION PERMISSIONS ====================

@sys_sec_permission_mgmt_router.post('/actions', response_model=ActionPermissionResponseDto, status_code=201)
async def create_action_permission(
        permission_request: ActionPermissionCreateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Create an action permission for a role
    """
    logger.info(f"Creating action permission: {permission_request.action_id} for role {permission_request.role_id}")

    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, permission_request.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permission = SysSecActionPermissionRepository.create(
            db,
            permission_request.role_id,
            permission_request.action_id
        )

        return ActionPermissionResponseDto(**permission)

    except Exception as e:
        logger.exception('Error creating action permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating action permission'
        )


@sys_sec_permission_mgmt_router.get('/actions/role/{role_id}', response_model=List[ActionPermissionResponseDto])
def get_role_action_permissions(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get all action permissions for a role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permissions = SysSecActionPermissionRepository.fetch_by_role(db, role_id)
        return [ActionPermissionResponseDto(**perm) for perm in permissions]

    except Exception as e:
        logger.exception('Error fetching action permissions')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching action permissions'
        )


@sys_sec_permission_mgmt_router.get('/actions/action/{action_id}')
def get_action_roles(action_id: str, db: Session = Depends(get_db)):
    """
    Get all roles that have a specific action permission
    """
    try:
        permissions = SysSecActionPermissionRepository.fetch_by_action(db, action_id)
        return {
            "action_id": action_id,
            "roles": permissions
        }

    except Exception as e:
        logger.exception('Error fetching action roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching action roles'
        )


@sys_sec_permission_mgmt_router.delete('/actions/{permission_id}')
async def delete_action_permission(
        permission_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Delete an action permission
    """
    try:
        success = SysSecActionPermissionRepository.delete(db, permission_id)

        if success:
            return {"message": "Action permission deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting action permission"
            )

    except Exception as e:
        logger.exception('Error deleting action permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error deleting action permission'
        )


@sys_sec_permission_mgmt_router.post('/actions/bulk', response_model=PermissionBatchResponseDto)
async def bulk_create_action_permissions(
        bulk_request: BulkPermissionCreateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Create multiple action permissions for a role at once
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, bulk_request.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        created_actions = SysSecActionPermissionRepository.bulk_create(
            db,
            bulk_request.role_id,
            bulk_request.permissions
        )

        return PermissionBatchResponseDto(
            created_count=len(created_actions),
            failed_count=len(bulk_request.permissions) - len(created_actions),
            errors=None
        )

    except Exception as e:
        logger.exception('Error in bulk create action permissions')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error in bulk create action permissions'
        )


# ==================== NAVIGATION PERMISSIONS ====================

@sys_sec_permission_mgmt_router.post('/navigation', response_model=NavigationPermissionResponseDto, status_code=201)
async def create_navigation_permission(
        permission_request: NavigationPermissionCreateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Create a navigation permission for a role
    """
    logger.info(f"Creating navigation permission: {permission_request.item_path} for role {permission_request.role_id}")

    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, permission_request.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permission = SysSecNavigationPermissionRepository.create(
            db,
            permission_request.role_id,
            permission_request.item_path,
            permission_request.navigate_state
        )

        return NavigationPermissionResponseDto(**permission)

    except Exception as e:
        logger.exception('Error creating navigation permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating navigation permission'
        )


@sys_sec_permission_mgmt_router.put('/navigation/{permission_id}', response_model=NavigationPermissionResponseDto)
async def update_navigation_permission(
        permission_id: UUID,
        navigate_state: int = Query(..., ge=0, le=1, description="0=Deny, 1=Allow"),
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Update navigation permission state
    """
    try:
        permission = SysSecNavigationPermissionRepository.update(db, permission_id, navigate_state)

        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Navigation permission not found"
            )

        return NavigationPermissionResponseDto(**permission)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error updating navigation permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating navigation permission'
        )


@sys_sec_permission_mgmt_router.get('/navigation/role/{role_id}', response_model=List[NavigationPermissionResponseDto])
def get_role_navigation_permissions(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get all navigation permissions for a role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permissions = SysSecNavigationPermissionRepository.fetch_by_role(db, role_id)
        return [NavigationPermissionResponseDto(**perm) for perm in permissions]

    except Exception as e:
        logger.exception('Error fetching navigation permissions')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching navigation permissions'
        )


@sys_sec_permission_mgmt_router.get('/navigation/path')
def get_path_roles(
        item_path: str = Query(..., description="Navigation path"),
        db: Session = Depends(get_db)
):
    """
    Get all roles that have permission for a specific navigation path
    """
    try:
        permissions = SysSecNavigationPermissionRepository.fetch_by_path(db, item_path)
        return {
            "item_path": item_path,
            "roles": permissions
        }

    except Exception as e:
        logger.exception('Error fetching path roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching path roles'
        )


@sys_sec_permission_mgmt_router.delete('/navigation/{permission_id}')
async def delete_navigation_permission(
        permission_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Delete a navigation permission
    """
    try:
        success = SysSecNavigationPermissionRepository.delete(db, permission_id)

        if success:
            return {"message": "Navigation permission deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting navigation permission"
            )

    except Exception as e:
        logger.exception('Error deleting navigation permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error deleting navigation permission'
        )


@sys_sec_permission_mgmt_router.post('/navigation/bulk', response_model=PermissionBatchResponseDto)
async def bulk_create_navigation_permissions(
        bulk_request: BulkPermissionCreateDto,
        navigate_state: int = Query(1, ge=0, le=1, description="0=Deny, 1=Allow"),
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Create multiple navigation permissions for a role at once
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, bulk_request.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        created_paths = SysSecNavigationPermissionRepository.bulk_create(
            db,
            bulk_request.role_id,
            bulk_request.permissions,
            navigate_state
        )

        return PermissionBatchResponseDto(
            created_count=len(created_paths),
            failed_count=len(bulk_request.permissions) - len(created_paths),
            errors=None
        )

    except Exception as e:
        logger.exception('Error in bulk create navigation permissions')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error in bulk create navigation permissions'
        )


# ==================== TYPE PERMISSIONS ====================

@sys_sec_permission_mgmt_router.post('/types', response_model=TypePermissionResponseDto, status_code=201)
async def create_type_permission(
        permission_request: TypePermissionCreateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Create a type permission for a role
    """
    logger.info(f"Creating type permission: {permission_request.target_type} for role {permission_request.role}")

    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, permission_request.role)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permission = SysSecTypePermissionRepository.create(
            db,
            permission_request.role,
            permission_request.target_type,
            permission_request.read_state,
            permission_request.write_state,
            permission_request.create_state,
            permission_request.delete_state,
            permission_request.navigate_state
        )

        return TypePermissionResponseDto(**permission)

    except Exception as e:
        logger.exception('Error creating type permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating type permission'
        )


@sys_sec_permission_mgmt_router.put('/types/{permission_id}', response_model=TypePermissionResponseDto)
async def update_type_permission(
        permission_id: UUID,
        read_state: Optional[int] = Query(None, ge=0, le=1),
        write_state: Optional[int] = Query(None, ge=0, le=1),
        create_state: Optional[int] = Query(None, ge=0, le=1),
        delete_state: Optional[int] = Query(None, ge=0, le=1),
        navigate_state: Optional[int] = Query(None, ge=0, le=1),
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Update type permission states
    """
    try:
        permission = SysSecTypePermissionRepository.update(
            db, permission_id,
            read_state, write_state, create_state, delete_state, navigate_state
        )

        if not permission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Type permission not found"
            )

        return TypePermissionResponseDto(**permission)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error updating type permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating type permission'
        )


@sys_sec_permission_mgmt_router.get('/types/role/{role_id}', response_model=List[TypePermissionResponseDto])
def get_role_type_permissions(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get all type permissions for a role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permissions = SysSecTypePermissionRepository.fetch_by_role(db, role_id)
        return [TypePermissionResponseDto(**perm) for perm in permissions]

    except Exception as e:
        logger.exception('Error fetching type permissions')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching type permissions'
        )


@sys_sec_permission_mgmt_router.get('/types/type/{target_type}')
def get_type_roles(target_type: str, db: Session = Depends(get_db)):
    """
    Get all roles that have permissions for a specific type
    """
    try:
        permissions = SysSecTypePermissionRepository.fetch_by_type(db, target_type)
        return {
            "target_type": target_type,
            "roles": permissions
        }

    except Exception as e:
        logger.exception('Error fetching type roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching type roles'
        )


@sys_sec_permission_mgmt_router.delete('/types/{permission_id}')
async def delete_type_permission(
        permission_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Delete a type permission
    """
    try:
        success = SysSecTypePermissionRepository.delete(db, permission_id)

        if success:
            return {"message": "Type permission deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting type permission"
            )

    except Exception as e:
        logger.exception('Error deleting type permission')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error deleting type permission'
        )


@sys_sec_permission_mgmt_router.post('/types/grant-full-access/{role_id}/{target_type}', response_model=TypePermissionResponseDto)
async def grant_full_access(
        role_id: UUID,
        target_type: str,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Grant full access (all CRUD operations) for a type to a role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permission = SysSecTypePermissionRepository.grant_full_access(db, role_id, target_type)
        return TypePermissionResponseDto(**permission)

    except Exception as e:
        logger.exception('Error granting full access')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error granting full access'
        )


@sys_sec_permission_mgmt_router.post('/types/grant-read-only/{role_id}/{target_type}', response_model=TypePermissionResponseDto)
async def grant_read_only(
        role_id: UUID,
        target_type: str,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Grant read-only access for a type to a role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        permission = SysSecTypePermissionRepository.grant_read_only(db, role_id, target_type)
        return TypePermissionResponseDto(**permission)

    except Exception as e:
        logger.exception('Error granting read-only access')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error granting read-only access'
        )


# ==================== UTILITY ENDPOINTS ====================

@sys_sec_permission_mgmt_router.get('/all-actions')
def get_all_actions(db: Session = Depends(get_db)):
    """
    Get all distinct action IDs in the system
    """
    try:
        actions = SysSecActionPermissionRepository.fetch_all_actions(db)
        return {"actions": actions}

    except Exception as e:
        logger.exception('Error fetching all actions')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching all actions'
        )


@sys_sec_permission_mgmt_router.get('/all-paths')
def get_all_paths(db: Session = Depends(get_db)):
    """
    Get all distinct navigation paths in the system
    """
    try:
        paths = SysSecNavigationPermissionRepository.fetch_all_paths(db)
        return {"paths": paths}

    except Exception as e:
        logger.exception('Error fetching all paths')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching all paths'
        )


@sys_sec_permission_mgmt_router.get('/all-types')
def get_all_types(db: Session = Depends(get_db)):
    """
    Get all distinct target types in the system
    """
    try:
        types = SysSecTypePermissionRepository.fetch_all_types(db)
        return {"types": types}

    except Exception as e:
        logger.exception('Error fetching all types')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching all types'
        )


@sys_sec_permission_mgmt_router.get('/role/{role_id}/summary')
def get_role_permissions_summary(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get comprehensive permissions summary for a role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        action_perms = SysSecActionPermissionRepository.fetch_by_role(db, role_id)
        nav_perms = SysSecNavigationPermissionRepository.fetch_by_role(db, role_id)
        type_perms = SysSecTypePermissionRepository.fetch_by_role(db, role_id)

        return {
            "role_id": str(role_id),
            "role_name": role['name'],
            "is_administrative": role['is_administrative'],
            "permissions": {
                "actions": [p['action_id'] for p in action_perms],
                "navigation": [
                    {
                        "path": p['item_path'],
                        "allowed": p['navigate_state'] == 1
                    }
                    for p in nav_perms
                ],
                "types": [
                    {
                        "type": p['target_type'],
                        "read": p['read_state'] == 1,
                        "write": p['write_state'] == 1,
                        "create": p['create_state'] == 1,
                        "delete": p['delete_state'] == 1,
                        "navigate": p['navigate_state'] == 1
                    }
                    for p in type_perms
                ]
            },
            "counts": {
                "actions": len(action_perms),
                "navigation": len(nav_perms),
                "types": len(type_perms)
            }
        }

    except Exception as e:
        logger.exception('Error fetching role permissions summary')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching role permissions summary'
        )
