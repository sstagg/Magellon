"""
Controller for Role Management API endpoints
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
    RoleCreateDto,
    RoleUpdateDto,
    RoleResponseDto
)
from repositories.security.sys_sec_role_repository import SysSecRoleRepository
from repositories.security.sys_sec_user_role_repository import SysSecUserRoleRepository

import logging

logger = logging.getLogger(__name__)

sys_sec_role_router = APIRouter()


def _to_role_response(role) -> RoleResponseDto:
    """Convert a SysSecRole ORM row to the response DTO."""
    return RoleResponseDto(
        oid=role.Oid,
        name=role.Name,
        is_administrative=role.IsAdministrative,
        can_edit_model=role.CanEditModel,
        permission_policy=role.PermissionPolicy
    )


@sys_sec_role_router.post('/', response_model=RoleResponseDto, status_code=201)
async def create_role(
        role_request: RoleCreateDto,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Create a new role

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    logger.info(f"Creating role: {role_request.name}")

    # Validate that role name doesn't already exist
    existing_role = SysSecRoleRepository.fetch_by_name(db, role_request.name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{role_request.name}' already exists"
        )

    with crud_guard(logger, 'Error creating role'):
        created_role = SysSecRoleRepository.create(
            db=db,
            role_dto=role_request,
            created_by=current_user_id
        )
        return _to_role_response(created_role)


@sys_sec_role_router.put('/', response_model=RoleResponseDto)
async def update_role(
        role_request: RoleUpdateDto,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Update an existing role

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    logger.info(f"Updating role: {role_request.oid}")

    # Check if role exists
    get_role_or_404(db, role_request.oid)

    # If name is being updated, check for conflicts
    if role_request.name:
        name_conflict = SysSecRoleRepository.fetch_by_name(db, role_request.name)
        if name_conflict and name_conflict.Oid != role_request.oid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Another role with name '{role_request.name}' already exists"
            )

    with crud_guard(logger, 'Error updating role'):
        updated_role = SysSecRoleRepository.update(
            db=db,
            role_dto=role_request,
            updated_by=current_user_id
        )
        # Historical behavior: this 404 was raised inside the try block, so
        # the guard converts it into the generic 500 (as the original did).
        found_or_404(updated_role, "Role not found")
        return _to_role_response(updated_role)


@sys_sec_role_router.get('/', response_model=List[RoleResponseDto])
def get_all_roles(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, le=1000),
        name: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get all roles with optional filtering and pagination

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    with crud_guard(logger, 'Error fetching roles'):
        if name:
            roles = SysSecRoleRepository.search_by_name(db, name, skip, limit)
        else:
            roles = SysSecRoleRepository.fetch_all(db, skip, limit)

        return [_to_role_response(role) for role in roles]


@sys_sec_role_router.get('/administrative', response_model=List[RoleResponseDto])
def get_administrative_roles(
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get all administrative roles

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    with crud_guard(logger, 'Error fetching administrative roles'):
        roles = SysSecRoleRepository.fetch_administrative_roles(db)
        return [_to_role_response(role) for role in roles]


@sys_sec_role_router.get('/{role_id}', response_model=RoleResponseDto)
def get_role(
        role_id: UUID,
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get role by ID

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    role = get_role_or_404(db, role_id)
    return _to_role_response(role)


@sys_sec_role_router.get('/name/{role_name}', response_model=RoleResponseDto)
def get_role_by_name(
        role_name: str,
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get role by name

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    role = found_or_404(SysSecRoleRepository.fetch_by_name(db, role_name), "Role not found")
    return _to_role_response(role)


@sys_sec_role_router.delete('/{role_id}')
async def delete_role(
        role_id: UUID,
        hard_delete: bool = Query(False),
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Delete role (soft delete by default, hard delete if specified)

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    get_role_or_404(db, role_id)

    # Check if role is assigned to any users
    user_count = SysSecUserRoleRepository.count_users_in_role(db, role_id)
    if user_count > 0 and hard_delete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot hard delete role. It is assigned to {user_count} user(s). Remove all user assignments first."
        )

    with crud_guard(logger, 'Error deleting role'):
        # If hard deleting, remove all user-role associations first
        if hard_delete:
            SysSecUserRoleRepository.remove_all_role_assignments(db, role_id)
            success = SysSecRoleRepository.hard_delete(db, role_id)
        else:
            success = SysSecRoleRepository.soft_delete(db, role_id)

        ensure_success(success, "Error deleting role")
        return {"message": f"Role {'permanently deleted' if hard_delete else 'deactivated'} successfully"}


@sys_sec_role_router.get('/{role_id}/users')
def get_role_users(
        role_id: UUID,
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get all users assigned to a role

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    role = get_role_or_404(db, role_id)

    with crud_guard(logger, 'Error fetching role users'):
        user_roles = SysSecUserRoleRepository.fetch_users_by_role(db, role_id)
        return {
            "role_id": role_id,
            "role_name": role.Name,
            "user_count": len(user_roles),
            "users": [
                {
                    "user_id": str(ur.People),
                    "username": ur.sys_sec_user.USERNAME,
                    "active": ur.sys_sec_user.ACTIVE,
                    "created_date": ur.sys_sec_user.created_date
                }
                for ur in user_roles
            ]
        }


@sys_sec_role_router.get('/stats/count')
def get_role_count(
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get total role count

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    count = SysSecRoleRepository.count_roles(db)
    return {
        "total_roles": count
    }


@sys_sec_role_router.get('/stats/summary')
def get_role_statistics(
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get comprehensive role statistics

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    with crud_guard(logger, 'Error fetching role statistics'):
        from models.sqlalchemy_models import SysSecRole, SysSecUserRole
        from sqlalchemy import func

        total_roles = SysSecRoleRepository.count_roles(db)
        admin_roles = SysSecRoleRepository.fetch_administrative_roles(db)

        # Count users per role using ORM
        roles_with_counts = db.query(
            SysSecRole.Oid,
            SysSecRole.Name,
            func.count(SysSecUserRole.People).label('user_count')
        ).outerjoin(
            SysSecUserRole, SysSecRole.Oid == SysSecUserRole.Roles
        ).filter(
            SysSecRole.GCRecord.is_(None)
        ).group_by(
            SysSecRole.Oid, SysSecRole.Name
        ).order_by(
            func.count(SysSecUserRole.People).desc()
        ).all()

        return {
            "total_roles": total_roles,
            "administrative_roles_count": len(admin_roles),
            "roles_with_user_counts": [
                {
                    "role_id": str(row.Oid),
                    "role_name": row.Name,
                    "user_count": row.user_count
                }
                for row in roles_with_counts
            ]
        }
