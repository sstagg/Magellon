"""
Controller for Role Management API endpoints
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
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


@sys_sec_role_router.post('/', response_model=RoleResponseDto, status_code=201)
async def create_role(
        role_request: RoleCreateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Create a new role
    """
    logger.info(f"Creating role: {role_request.name}")

    # Validate that role name doesn't already exist
    existing_role = SysSecRoleRepository.fetch_by_name(db, role_request.name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role with name '{role_request.name}' already exists"
        )

    try:
        created_role = SysSecRoleRepository.create(
            db=db,
            role_dto=role_request,
            created_by=current_user_id
        )

        return RoleResponseDto(
            oid=created_role.Oid,
            name=created_role.Name,
            is_administrative=created_role.IsAdministrative,
            can_edit_model=created_role.CanEditModel,
            permission_policy=created_role.PermissionPolicy
        )

    except Exception as e:
        logger.exception('Error creating role')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating role'
        )


@sys_sec_role_router.put('/', response_model=RoleResponseDto)
async def update_role(
        role_request: RoleUpdateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Update an existing role
    """
    logger.info(f"Updating role: {role_request.oid}")

    # Check if role exists
    existing_role = SysSecRoleRepository.fetch_by_id(db, role_request.oid)
    if not existing_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # If name is being updated, check for conflicts
    if role_request.name:
        name_conflict = SysSecRoleRepository.fetch_by_name(db, role_request.name)
        if name_conflict and name_conflict.Oid != role_request.oid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Another role with name '{role_request.name}' already exists"
            )

    try:
        updated_role = SysSecRoleRepository.update(
            db=db,
            role_dto=role_request,
            updated_by=current_user_id
        )

        if not updated_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        return RoleResponseDto(
            oid=updated_role.Oid,
            name=updated_role.Name,
            is_administrative=updated_role.IsAdministrative,
            can_edit_model=updated_role.CanEditModel,
            permission_policy=updated_role.PermissionPolicy
        )

    except Exception as e:
        logger.exception('Error updating role')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating role'
        )


@sys_sec_role_router.get('/', response_model=List[RoleResponseDto])
def get_all_roles(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, le=1000),
        name: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
        db: Session = Depends(get_db)
):
    """
    Get all roles with optional filtering and pagination
    """
    try:
        if name:
            roles = SysSecRoleRepository.search_by_name(db, name, skip, limit)
        else:
            roles = SysSecRoleRepository.fetch_all(db, skip, limit)

        return [
            RoleResponseDto(
                oid=role.Oid,
                name=role.Name,
                is_administrative=role.IsAdministrative,
                can_edit_model=role.CanEditModel,
                permission_policy=role.PermissionPolicy
            )
            for role in roles
        ]

    except Exception as e:
        logger.exception('Error fetching roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching roles'
        )


@sys_sec_role_router.get('/administrative', response_model=List[RoleResponseDto])
def get_administrative_roles(db: Session = Depends(get_db)):
    """
    Get all administrative roles
    """
    try:
        roles = SysSecRoleRepository.fetch_administrative_roles(db)
        return [
            RoleResponseDto(
                oid=role.Oid,
                name=role.Name,
                is_administrative=role.IsAdministrative,
                can_edit_model=role.CanEditModel,
                permission_policy=role.PermissionPolicy
            )
            for role in roles
        ]

    except Exception as e:
        logger.exception('Error fetching administrative roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching administrative roles'
        )


@sys_sec_role_router.get('/{role_id}', response_model=RoleResponseDto)
def get_role(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get role by ID
    """
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return RoleResponseDto(
        oid=role.Oid,
        name=role.Name,
        is_administrative=role.IsAdministrative,
        can_edit_model=role.CanEditModel,
        permission_policy=role.PermissionPolicy
    )


@sys_sec_role_router.get('/name/{role_name}', response_model=RoleResponseDto)
def get_role_by_name(role_name: str, db: Session = Depends(get_db)):
    """
    Get role by name
    """
    role = SysSecRoleRepository.fetch_by_name(db, role_name)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return RoleResponseDto(
        oid=role.Oid,
        name=role.Name,
        is_administrative=role.IsAdministrative,
        can_edit_model=role.CanEditModel,
        permission_policy=role.PermissionPolicy
    )


@sys_sec_role_router.delete('/{role_id}')
async def delete_role(
        role_id: UUID,
        hard_delete: bool = Query(False),
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Delete role (soft delete by default, hard delete if specified)
    """
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check if role is assigned to any users
    user_count = SysSecUserRoleRepository.count_users_in_role(db, role_id)
    if user_count > 0 and hard_delete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot hard delete role. It is assigned to {user_count} user(s). Remove all user assignments first."
        )

    try:
        # If hard deleting, remove all user-role associations first
        if hard_delete:
            SysSecUserRoleRepository.remove_all_role_assignments(db, role_id)
            success = await SysSecRoleRepository.hard_delete(db, role_id)
        else:
            success = await SysSecRoleRepository.soft_delete(db, role_id)

        if success:
            return {"message": f"Role {'permanently deleted' if hard_delete else 'deactivated'} successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting role"
            )

    except Exception as e:
        logger.exception('Error deleting role')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error deleting role'
        )


@sys_sec_role_router.get('/{role_id}/users')
def get_role_users(
        role_id: UUID,
        db: Session = Depends(get_db)
):
    """
    Get all users assigned to a role
    """
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
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

    except Exception as e:
        logger.exception('Error fetching role users')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching role users'
        )


@sys_sec_role_router.get('/stats/count')
def get_role_count(db: Session = Depends(get_db)):
    """
    Get total role count
    """
    count = SysSecRoleRepository.count_roles(db)
    return {
        "total_roles": count
    }


@sys_sec_role_router.get('/stats/summary')
def get_role_statistics(db: Session = Depends(get_db)):
    """
    Get comprehensive role statistics
    """
    try:
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

    except Exception as e:
        logger.exception('Error fetching role statistics')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching role statistics'
        )
