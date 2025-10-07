"""
Controller for User-Role Management API endpoints
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from models.security.security_models import (
    UserRoleCreateDto,
    UserRoleResponseDto,
    UserRoleDetailDto,
    BulkRoleAssignmentDto
)
from repositories.security.sys_sec_user_role_repository import SysSecUserRoleRepository
from repositories.security.sys_sec_role_repository import SysSecRoleRepository
from repositories.security.sys_sec_user_repository import SysSecUserRepository

import logging

logger = logging.getLogger(__name__)

sys_sec_user_role_router = APIRouter()


@sys_sec_user_role_router.post('/', response_model=UserRoleResponseDto, status_code=201)
async def assign_role_to_user(
        assignment_request: UserRoleCreateDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Assign a role to a user
    """
    user_id = assignment_request.user_id
    role_id = assignment_request.role_id

    logger.info(f"Assigning role {role_id} to user {user_id}")

    # Validate user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        assignment = SysSecUserRoleRepository.assign_role_to_user(db, user_id, role_id)
        return UserRoleResponseDto(**assignment)

    except Exception as e:
        logger.exception('Error assigning role to user')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error assigning role to user'
        )


@sys_sec_user_role_router.delete('/user/{user_id}/role/{role_id}')
async def remove_role_from_user(
        user_id: UUID,
        role_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Remove a role from a user
    """
    logger.info(f"Removing role {role_id} from user {user_id}")

    # Check if assignment exists
    assignment = SysSecUserRoleRepository.fetch_by_user_and_role(db, user_id, role_id)
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User-role assignment not found"
        )

    try:
        success = SysSecUserRoleRepository.remove_role_from_user(db, user_id, role_id)

        if success:
            return {"message": "Role removed from user successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error removing role from user"
            )

    except Exception as e:
        logger.exception('Error removing role from user')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error removing role from user'
        )


@sys_sec_user_role_router.get('/user/{user_id}/roles', response_model=List[UserRoleDetailDto])
def get_user_roles(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get all roles assigned to a user with role details
    """
    # Validate user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        user_roles = SysSecUserRoleRepository.fetch_roles_by_user(db, user_id)
        return [
            UserRoleDetailDto(
                oid=ur.oid,
                user_id=ur.People,
                role_id=ur.Roles,
                role_name=ur.sys_sec_role.Name,
                is_administrative=ur.sys_sec_role.IsAdministrative,
                can_edit_model=ur.sys_sec_role.CanEditModel
            )
            for ur in user_roles
        ]

    except Exception as e:
        logger.exception('Error fetching user roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching user roles'
        )


@sys_sec_user_role_router.get('/role/{role_id}/users')
def get_role_users(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get all users assigned to a role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
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
                    "active": ur.sys_sec_user.ACTIVE
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


@sys_sec_user_role_router.get('/', response_model=List[dict])
def get_all_user_roles(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, le=1000),
        db: Session = Depends(get_db)
):
    """
    Get all user-role assignments with details
    """
    try:
        assignments = SysSecUserRoleRepository.fetch_all_user_roles(db, skip, limit)
        return assignments

    except Exception as e:
        logger.exception('Error fetching user-role assignments')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching user-role assignments'
        )


@sys_sec_user_role_router.delete('/user/{user_id}/roles')
async def remove_all_user_roles(
        user_id: UUID,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Remove all roles from a user
    """
    logger.info(f"Removing all roles from user {user_id}")

    # Validate user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        success = SysSecUserRoleRepository.remove_all_user_roles(db, user_id)

        if success:
            return {"message": "All roles removed from user successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error removing roles from user"
            )

    except Exception as e:
        logger.exception('Error removing all user roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error removing all user roles'
        )


@sys_sec_user_role_router.post('/bulk-assign', status_code=201)
async def bulk_assign_role(
        bulk_request: BulkRoleAssignmentDto,
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Assign a role to multiple users at once
    """
    logger.info(f"Bulk assigning role {bulk_request.role_id} to {len(bulk_request.user_ids)} users")

    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, bulk_request.role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Validate all users exist
    for user_id in bulk_request.user_ids:
        user = SysSecUserRepository.fetch_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {user_id}"
            )

    try:
        assigned_users = SysSecUserRoleRepository.bulk_assign_roles(
            db,
            bulk_request.user_ids,
            bulk_request.role_id
        )

        return {
            "message": "Bulk role assignment successful",
            "role_id": bulk_request.role_id,
            "role_name": role.Name,
            "total_requested": len(bulk_request.user_ids),
            "newly_assigned": len(assigned_users),
            "already_assigned": len(bulk_request.user_ids) - len(assigned_users)
        }

    except Exception as e:
        logger.exception('Error in bulk role assignment')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error in bulk role assignment'
        )


@sys_sec_user_role_router.put('/user/{user_id}/sync-roles')
async def sync_user_roles(
        user_id: UUID,
        role_ids: List[UUID],
        db: Session = Depends(get_db),
        current_user_id: Optional[UUID] = None
):
    """
    Synchronize user roles - replaces all user roles with the provided list
    """
    logger.info(f"Syncing roles for user {user_id}")

    # Validate user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Validate all roles exist
    for role_id in role_ids:
        role = SysSecRoleRepository.fetch_by_id(db, role_id)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role not found: {role_id}"
            )

    try:
        result = SysSecUserRoleRepository.sync_user_roles(db, user_id, role_ids)

        return {
            "message": "User roles synchronized successfully",
            "user_id": user_id,
            "roles_added": result['added'],
            "roles_removed": result['removed'],
            "total_roles": len(role_ids)
        }

    except Exception as e:
        logger.exception('Error syncing user roles')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error syncing user roles'
        )


@sys_sec_user_role_router.get('/user/{user_id}/has-role/{role_name}')
def check_user_has_role(
        user_id: UUID,
        role_name: str,
        db: Session = Depends(get_db)
):
    """
    Check if a user has a specific role by role name
    """
    # Validate user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        has_role = SysSecUserRoleRepository.user_has_role(db, user_id, role_name)
        return {
            "user_id": user_id,
            "role_name": role_name,
            "has_role": has_role
        }

    except Exception as e:
        logger.exception('Error checking user role')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking user role'
        )


@sys_sec_user_role_router.get('/user/{user_id}/is-admin')
def check_user_is_admin(user_id: UUID, db: Session = Depends(get_db)):
    """
    Check if a user has any administrative role
    """
    # Validate user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        is_admin = SysSecUserRoleRepository.user_has_any_administrative_role(db, user_id)
        return {
            "user_id": user_id,
            "is_admin": is_admin
        }

    except Exception as e:
        logger.exception('Error checking admin status')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error checking admin status'
        )


@sys_sec_user_role_router.get('/stats/user/{user_id}')
def get_user_role_stats(user_id: UUID, db: Session = Depends(get_db)):
    """
    Get role statistics for a specific user
    """
    # Validate user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        role_count = SysSecUserRoleRepository.count_roles_for_user(db, user_id)
        is_admin = SysSecUserRoleRepository.user_has_any_administrative_role(db, user_id)
        roles = SysSecUserRoleRepository.fetch_roles_by_user(db, user_id)

        return {
            "user_id": user_id,
            "username": user.USERNAME,
            "total_roles": role_count,
            "is_admin": is_admin,
            "roles": [
                {
                    "role_id": role['role_id'],
                    "role_name": role['role_name'],
                    "is_administrative": role['is_administrative']
                }
                for role in roles
            ]
        }

    except Exception as e:
        logger.exception('Error fetching user role statistics')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching user role statistics'
        )


@sys_sec_user_role_router.get('/stats/role/{role_id}')
def get_role_assignment_stats(role_id: UUID, db: Session = Depends(get_db)):
    """
    Get assignment statistics for a specific role
    """
    # Validate role exists
    role = SysSecRoleRepository.fetch_by_id(db, role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    try:
        user_count = SysSecUserRoleRepository.count_users_in_role(db, role_id)

        return {
            "role_id": role_id,
            "role_name": role['name'],
            "is_administrative": role['is_administrative'],
            "total_users": user_count
        }

    except Exception as e:
        logger.exception('Error fetching role assignment statistics')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching role assignment statistics'
        )
