"""
Controller for Permission Management API endpoints (Action, Navigation, Type)
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from controllers.security._crud_helpers import (
    crud_guard,
    ensure_success,
    found_or_404,
    get_role_or_404,
)
from database import get_db
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_role
from models.security.security_models import (
    ActionPermissionCreateDto,
    ActionPermissionResponseDto,
    NavigationPermissionCreateDto,
    NavigationPermissionResponseDto,
    TypePermissionCreateDto,
    TypePermissionResponseDto,
    BulkPermissionCreateDto,
    PermissionBatchResponseDto, ObjectPermissionCreateDto, ObjectPermissionResponseDto
)
from repositories.security.sys_sec_action_permission_repository import SysSecActionPermissionRepository
from repositories.security.sys_sec_navigation_permission_repository import SysSecNavigationPermissionRepository
from repositories.security.sys_sec_object_permission_repository import SysSecObjectPermissionRepository
from repositories.security.sys_sec_type_permission_repository import SysSecTypePermissionRepository

import logging

logger = logging.getLogger(__name__)

sys_sec_permission_mgmt_router = APIRouter(
    dependencies=[
        Depends(get_current_user_id),
        Depends(require_role('Administrator')),
    ]
)


def _to_action_permission_response(perm) -> ActionPermissionResponseDto:
    """Convert a SysSecActionPermission ORM row to the response DTO."""
    return ActionPermissionResponseDto(
        oid=perm.Oid,
        action_id=perm.ActionId,
        role_id=perm.Role,
        optimistic_lock_field=perm.OptimisticLockField,
        gc_record=perm.GCRecord if hasattr(perm, 'GCRecord') else None
    )


def _to_navigation_permission_response(perm) -> NavigationPermissionResponseDto:
    """Convert a SysSecNavigationPermission ORM row to the response DTO."""
    return NavigationPermissionResponseDto(
        oid=perm.Oid,
        item_path=perm.ItemPath,
        navigate_state=perm.NavigateState,
        role_id=perm.Role,
        optimistic_lock_field=perm.OptimisticLockField,
        gc_record=perm.GCRecord if hasattr(perm, 'GCRecord') else None
    )


def _to_type_permission_response(perm) -> TypePermissionResponseDto:
    """Convert a SysSecTypePermission ORM row to the response DTO."""
    return TypePermissionResponseDto(
        oid=perm.Oid,
        target_type=perm.TargetType,
        role=perm.Role,
        read_state=perm.ReadState,
        write_state=perm.WriteState,
        create_state=perm.CreateState,
        delete_state=perm.DeleteState,
        navigate_state=perm.NavigateState,
        optimistic_lock_field=perm.OptimisticLockField,
        gc_record=perm.GCRecord if hasattr(perm, 'GCRecord') else None
    )


def _to_object_permission_response(perm) -> ObjectPermissionResponseDto:
    """Convert a SysSecObjectPermission ORM row to the response DTO."""
    return ObjectPermissionResponseDto(
        oid=perm.oid,
        criteria=perm.Criteria or "",
        read_state=perm.ReadState or 0,
        write_state=perm.WriteState or 0,
        delete_state=perm.DeleteState or 0,
        navigate_state=perm.NavigateState or 0,
        type_permission_object=perm.TypePermissionObject,
        optimistic_lock_field=perm.OptimisticLockField,
        gc_record=perm.GCRecord
    )


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

    get_role_or_404(db, permission_request.role_id)

    with crud_guard(logger, 'Error creating action permission'):
        permission = SysSecActionPermissionRepository.create(
            db,
            permission_request.role_id,
            permission_request.action_id
        )
        return _to_action_permission_response(permission)


@sys_sec_permission_mgmt_router.get('/actions/role/{role_id}', response_model=List[ActionPermissionResponseDto])
def get_role_action_permissions(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get all action permissions for a role
    """
    get_role_or_404(db, role_id)

    with crud_guard(logger, 'Error fetching action permissions'):
        permissions = SysSecActionPermissionRepository.fetch_by_role(db, role_id)
        return [_to_action_permission_response(perm) for perm in permissions]


@sys_sec_permission_mgmt_router.get('/actions/action/{action_id}')
def get_action_roles(action_id: str, db: Session = Depends(get_db)):
    """
    Get all roles that have a specific action permission
    """
    with crud_guard(logger, 'Error fetching action roles'):
        permissions = SysSecActionPermissionRepository.fetch_by_action(db, action_id)
        return {
            "action_id": action_id,
            "roles": permissions
        }


@sys_sec_permission_mgmt_router.delete('/actions/{permission_id}')
async def delete_action_permission(
        permission_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Delete an action permission
    """
    with crud_guard(logger, 'Error deleting action permission'):
        success = SysSecActionPermissionRepository.delete(db, permission_id)
        ensure_success(success, "Error deleting action permission")
        return {"message": "Action permission deleted successfully"}


@sys_sec_permission_mgmt_router.post('/actions/bulk', response_model=PermissionBatchResponseDto)
async def bulk_create_action_permissions(
        bulk_request: BulkPermissionCreateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Create multiple action permissions for a role at once
    """
    get_role_or_404(db, bulk_request.role_id)

    with crud_guard(logger, 'Error in bulk create action permissions'):
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

    get_role_or_404(db, permission_request.role_id)

    with crud_guard(logger, 'Error creating navigation permission'):
        permission = SysSecNavigationPermissionRepository.create(
            db,
            permission_request.role_id,
            permission_request.item_path,
            permission_request.navigate_state
        )
        return _to_navigation_permission_response(permission)


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
    with crud_guard(logger, 'Error updating navigation permission', reraise_http=True):
        permission = SysSecNavigationPermissionRepository.update(db, permission_id, navigate_state)
        found_or_404(permission, "Navigation permission not found")
        return _to_navigation_permission_response(permission)


@sys_sec_permission_mgmt_router.get('/navigation/role/{role_id}', response_model=List[NavigationPermissionResponseDto])
def get_role_navigation_permissions(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get all navigation permissions for a role
    """
    get_role_or_404(db, role_id)

    with crud_guard(logger, 'Error fetching navigation permissions'):
        permissions = SysSecNavigationPermissionRepository.fetch_by_role(db, role_id)
        return [_to_navigation_permission_response(perm) for perm in permissions]


@sys_sec_permission_mgmt_router.get('/navigation/path')
def get_path_roles(
        item_path: str = Query(..., description="Navigation path"),
        db: Session = Depends(get_db)
):
    """
    Get all roles that have permission for a specific navigation path
    """
    with crud_guard(logger, 'Error fetching path roles'):
        permissions = SysSecNavigationPermissionRepository.fetch_by_path(db, item_path)
        return {
            "item_path": item_path,
            "roles": permissions
        }


@sys_sec_permission_mgmt_router.delete('/navigation/{permission_id}')
async def delete_navigation_permission(
        permission_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Delete a navigation permission
    """
    with crud_guard(logger, 'Error deleting navigation permission'):
        success = SysSecNavigationPermissionRepository.delete(db, permission_id)
        ensure_success(success, "Error deleting navigation permission")
        return {"message": "Navigation permission deleted successfully"}


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
    get_role_or_404(db, bulk_request.role_id)

    with crud_guard(logger, 'Error in bulk create navigation permissions'):
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

    get_role_or_404(db, permission_request.role)

    with crud_guard(logger, 'Error creating type permission'):
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
        return _to_type_permission_response(permission)


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
    with crud_guard(logger, 'Error updating type permission', reraise_http=True):
        permission = SysSecTypePermissionRepository.update(
            db, permission_id,
            read_state, write_state, create_state, delete_state, navigate_state
        )
        found_or_404(permission, "Type permission not found")
        return _to_type_permission_response(permission)


@sys_sec_permission_mgmt_router.get('/types/role/{role_id}', response_model=List[TypePermissionResponseDto])
def get_role_type_permissions(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get all type permissions for a role
    """
    get_role_or_404(db, role_id)

    with crud_guard(logger, 'Error fetching type permissions'):
        permissions = SysSecTypePermissionRepository.fetch_by_role(db, role_id)
        return [_to_type_permission_response(perm) for perm in permissions]


@sys_sec_permission_mgmt_router.get('/types/type/{target_type}')
def get_type_roles(target_type: str, db: Session = Depends(get_db)):
    """
    Get all roles that have permissions for a specific type
    """
    with crud_guard(logger, 'Error fetching type roles'):
        permissions = SysSecTypePermissionRepository.fetch_by_type(db, target_type)
        return {
            "target_type": target_type,
            "roles": permissions
        }


@sys_sec_permission_mgmt_router.delete('/types/{permission_id}')
async def delete_type_permission(
        permission_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Delete a type permission
    """
    with crud_guard(logger, 'Error deleting type permission'):
        success = SysSecTypePermissionRepository.delete(db, permission_id)
        ensure_success(success, "Error deleting type permission")
        return {"message": "Type permission deleted successfully"}


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
    get_role_or_404(db, role_id)

    with crud_guard(logger, 'Error granting full access'):
        permission = SysSecTypePermissionRepository.grant_full_access(db, role_id, target_type)
        return _to_type_permission_response(permission)


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
    get_role_or_404(db, role_id)

    with crud_guard(logger, 'Error granting read-only access'):
        permission = SysSecTypePermissionRepository.grant_read_only(db, role_id, target_type)
        return _to_type_permission_response(permission)


# ==================== UTILITY ENDPOINTS ====================

@sys_sec_permission_mgmt_router.get('/all-actions')
def get_all_actions(db: Session = Depends(get_db)):
    """
    Get all distinct action IDs in the system
    """
    with crud_guard(logger, 'Error fetching all actions'):
        actions = SysSecActionPermissionRepository.fetch_all_actions(db)
        return {"actions": actions}


@sys_sec_permission_mgmt_router.get('/all-paths')
def get_all_paths(db: Session = Depends(get_db)):
    """
    Get all distinct navigation paths in the system
    """
    with crud_guard(logger, 'Error fetching all paths'):
        paths = SysSecNavigationPermissionRepository.fetch_all_paths(db)
        return {"paths": paths}


@sys_sec_permission_mgmt_router.get('/all-types')
def get_all_types(db: Session = Depends(get_db)):
    """
    Get all distinct target types in the system
    """
    with crud_guard(logger, 'Error fetching all types'):
        types = SysSecTypePermissionRepository.fetch_all_types(db)
        return {"types": types}


@sys_sec_permission_mgmt_router.get('/role/{role_id}/summary')
def get_role_permissions_summary(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get comprehensive permissions summary for a role
    """
    role = get_role_or_404(db, role_id)

    with crud_guard(logger, 'Error fetching role permissions summary'):
        action_perms = SysSecActionPermissionRepository.fetch_by_role(db, role_id)
        nav_perms = SysSecNavigationPermissionRepository.fetch_by_role(db, role_id)
        type_perms = SysSecTypePermissionRepository.fetch_by_role(db, role_id)

        return {
            "role_id": str(role_id),
            "role_name": role.Name,
            "is_administrative": role.IsAdministrative,
            "permissions": {
                "actions": [p.ActionId for p in action_perms],
                "navigation": [
                    {
                        "path": p.ItemPath,
                        "allowed": p.NavigateState == 1
                    }
                    for p in nav_perms
                ],
                "types": [
                    {
                        "type": p.TargetType,
                        "read": p.ReadState == 1,
                        "write": p.WriteState == 1,
                        "create": p.CreateState == 1,
                        "delete": p.DeleteState == 1,
                        "navigate": p.NavigateState == 1
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


# ==================== OBJECT PERMISSIONS (Record-Based) ====================

@sys_sec_permission_mgmt_router.get('/permissions/objects/type/{type_permission_id}', response_model=List[ObjectPermissionResponseDto])
async def get_type_object_permissions(
        type_permission_id: UUID,
        db: Session = Depends(get_db),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator'))
):
    """
    Get all object permissions for a specific type permission.
    Object permissions define criteria-based record-level access control.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    with crud_guard(logger, 'Error fetching object permissions', append_error=True):
        permissions = SysSecObjectPermissionRepository.fetch_by_type_permission(db, type_permission_id)
        return [_to_object_permission_response(perm) for perm in permissions]


@sys_sec_permission_mgmt_router.post('/permissions/objects', response_model=ObjectPermissionResponseDto, status_code=201)
async def create_object_permission(
        permission_request: ObjectPermissionCreateDto,
        db: Session = Depends(get_db),
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator'))
):
    """
    Create an object permission with criteria-based filtering.

    **Example Criteria:**
    - `[user_id] = CurrentUserId()` - Users can only see their own records
    - `[owner_id] = CurrentUserId() OR [assigned_to] = CurrentUserId()` - Users can see records they own or are assigned to
    - `[status] = 'active'` - Only active records
    - `[department_id] = CurrentUser().Department` - Records from user's department

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    logger.info(f"Creating object permission for type permission {permission_request.type_permission_object}")

    # Validate type permission exists
    found_or_404(
        SysSecTypePermissionRepository.fetch_by_id(db, permission_request.type_permission_object),
        "Type permission not found"
    )

    with crud_guard(logger, 'Error creating object permission', append_error=True):
        permission = SysSecObjectPermissionRepository.create(
            db=db,
            type_permission_id=permission_request.type_permission_object,
            criteria=permission_request.criteria or "",
            read_state=permission_request.read_state,
            write_state=permission_request.write_state,
            delete_state=permission_request.delete_state,
            navigate_state=permission_request.navigate_state
        )
        return _to_object_permission_response(permission)


@sys_sec_permission_mgmt_router.put('/permissions/objects/{permission_id}', response_model=ObjectPermissionResponseDto)
async def update_object_permission(
        permission_id: UUID,
        permission_request: ObjectPermissionCreateDto,
        db: Session = Depends(get_db),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator'))
):
    """
    Update an object permission.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    with crud_guard(logger, 'Error updating object permission', reraise_http=True, append_error=True):
        permission = SysSecObjectPermissionRepository.update(
            db=db,
            permission_id=permission_id,
            criteria=permission_request.criteria,
            read_state=permission_request.read_state,
            write_state=permission_request.write_state,
            delete_state=permission_request.delete_state,
            navigate_state=permission_request.navigate_state
        )

        found_or_404(permission, "Object permission not found")
        return _to_object_permission_response(permission)


@sys_sec_permission_mgmt_router.delete('/permissions/objects/{permission_id}')
async def delete_object_permission(
        permission_id: UUID,
        hard_delete: bool = False,
        db: Session = Depends(get_db),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator'))
):
    """
    Delete an object permission (soft delete by default).

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    with crud_guard(logger, 'Error deleting object permission', reraise_http=True, append_error=True):
        success = SysSecObjectPermissionRepository.delete(db, permission_id, hard_delete=hard_delete)

        # Unlike the other delete routes, a falsy result here means the row
        # did not exist, so it maps to 404 (passed through by reraise_http).
        found_or_404(success, "Object permission not found")
        return {"message": "Object permission deleted successfully"}
