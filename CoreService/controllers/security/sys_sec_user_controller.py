from typing import List, Optional
from datetime import datetime, timedelta
from uuid import UUID
import bcrypt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_permission, require_role
from models.pydantic_models import (
    SysSecUserCreateDto,
    SysSecUserUpdateDto,
    SysSecUserResponseDto,
    PasswordHashRequest
)
from repositories.security.sys_sec_user_repository import SysSecUserRepository

import logging

logger = logging.getLogger(__name__)

sys_sec_user_router = APIRouter()


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt
    """
    # Generate salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against bcrypt hash
    """
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


@sys_sec_user_router.post('/', response_model=SysSecUserResponseDto, status_code=201)
async def create_user(
        user_request: SysSecUserCreateDto,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Create a new user

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    logger.info(f"Creating user: {user_request.username}")

    # Validate input data
    if not user_request.username or not user_request.username.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Username cannot be empty'
        )

    # Check if user already exists
    existing_user = SysSecUserRepository.fetch_by_username(db, user_request.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists with this username"
        )

    try:
        # Hash password
        user_request.password = hash_password(user_request.password)

        # Create user in the database
        created_user = await SysSecUserRepository.create(
            db=db,
            user_dto=user_request,
            created_by=current_user_id
        )

        # Convert to response DTO with proper field mapping
        response_data = {
            "oid": created_user.oid,
            "USERNAME": created_user.USERNAME,
            "ACTIVE": created_user.ACTIVE,
            "created_date": created_user.created_date,
            "last_modified_date": created_user.last_modified_date,
            "omid": created_user.omid,
            "ouid": created_user.ouid,
            "sync_status": created_user.sync_status,
            "version": created_user.version,
            "ChangePasswordOnFirstLogon": created_user.ChangePasswordOnFirstLogon,
            "ObjectType": created_user.ObjectType,
            "AccessFailedCount": created_user.AccessFailedCount,
            "LockoutEnd": created_user.LockoutEnd
        }

        return SysSecUserResponseDto(**response_data)

    except Exception as e:
        logger.exception('Error creating user in database')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating user'
        )


@sys_sec_user_router.put('/', response_model=SysSecUserResponseDto, status_code=200)
async def update_user(
        user_request: SysSecUserUpdateDto,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Update an existing user

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    logger.info(f"Updating user: {user_request.oid}")

    # Hash password if provided
    if user_request.password:
        user_request.password = hash_password(user_request.password)

    try:
        updated_user = await SysSecUserRepository.update(
            db=db,
            user_dto=user_request,
            updated_by=current_user_id
        )

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Convert to response DTO with proper field mapping
        response_data = {
            "oid": updated_user.oid,
            "USERNAME": updated_user.USERNAME,
            "ACTIVE": updated_user.ACTIVE,
            "created_date": updated_user.created_date,
            "last_modified_date": updated_user.last_modified_date,
            "omid": updated_user.omid,
            "ouid": updated_user.ouid,
            "sync_status": updated_user.sync_status,
            "version": updated_user.version,
            "ChangePasswordOnFirstLogon": updated_user.ChangePasswordOnFirstLogon,
            "ObjectType": updated_user.ObjectType,
            "AccessFailedCount": updated_user.AccessFailedCount,
            "LockoutEnd": updated_user.LockoutEnd
        }

        return SysSecUserResponseDto(**response_data)

    except Exception as e:
        logger.exception('Error updating user in database')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating user'
        )


def _convert_user_to_response_dto(user) -> SysSecUserResponseDto:
    """
    Helper function to convert SQLAlchemy user model to response DTO
    """
    return SysSecUserResponseDto(
        oid=user.oid,
        USERNAME=user.USERNAME,
        ACTIVE=user.ACTIVE,
        created_date=user.created_date,
        last_modified_date=user.last_modified_date,
        omid=user.omid,
        ouid=user.ouid,
        sync_status=user.sync_status,
        version=user.version,
        ChangePasswordOnFirstLogon=user.ChangePasswordOnFirstLogon,
        ObjectType=user.ObjectType,
        AccessFailedCount=user.AccessFailedCount,
        LockoutEnd=user.LockoutEnd
    )


@sys_sec_user_router.get('/', response_model=List[SysSecUserResponseDto])
def get_all_users(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, le=1000),
        username: Optional[str] = None,
        include_inactive: bool = Query(False),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get all users with optional filtering and pagination

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    try:
        if username:
            users = SysSecUserRepository.search_by_username(db, username, skip, limit)
        else:
            users = SysSecUserRepository.fetch_all(db, skip, limit, include_inactive)

        return [_convert_user_to_response_dto(user) for user in users]

    except Exception as e:
        logger.exception('Error fetching users from database')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error fetching users'
        )


@sys_sec_user_router.get('/{user_id}', response_model=SysSecUserResponseDto)
def get_user(
        user_id: UUID,
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get user by ID

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    db_user = SysSecUserRepository.fetch_by_id(db, user_id)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return _convert_user_to_response_dto(db_user)


@sys_sec_user_router.get('/username/{username}', response_model=SysSecUserResponseDto)
def get_user_by_username(
        username: str,
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get user by username

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    db_user = SysSecUserRepository.fetch_by_username(db, username)
    if db_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return _convert_user_to_response_dto(db_user)


@sys_sec_user_router.delete('/{user_id}')
async def delete_user(
        user_id: UUID,
        hard_delete: bool = Query(False),
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Delete user (soft delete by default, hard delete if specified)

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        if hard_delete:
            success = await SysSecUserRepository.hard_delete(db, user_id)
        else:
            success = await SysSecUserRepository.soft_delete(db, user_id, current_user_id)

        if success:
            return {"message": "User deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error deleting user"
            )

    except Exception as e:
        logger.exception('Error deleting user')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_SERVER_ERROR,
            detail='Error deleting user'
        )


@sys_sec_user_router.post('/authenticate')
async def authenticate_user(
        username: str,
        password: str,
        db: Session = Depends(get_db)
):
    """
    Authenticate user with username and password
    """
    # Check if user exists and is active
    user = SysSecUserRepository.fetch_active_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Check if user is locked out
    if SysSecUserRepository.is_locked_out(db, user.oid):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account is locked due to too many failed attempts"
        )

    # Verify password
    if not verify_password(password, user.PASSWORD):
        # Increment failed access count
        await SysSecUserRepository.increment_failed_access(db, user.oid)

        # Lock account after 5 failed attempts
        if (user.AccessFailedCount or 0) >= 4:  # Will be 5 after increment
            lockout_end = datetime.now() + timedelta(minutes=30)
            await SysSecUserRepository.set_lockout(db, user.oid, lockout_end)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Reset failed access count on successful login
    await SysSecUserRepository.reset_failed_access(db, user.oid)

    return {
        "message": "Authentication successful",
        "user_id": str(user.oid),
        "username": user.USERNAME,
        "change_password_required": user.ChangePasswordOnFirstLogon
    }


@sys_sec_user_router.post('/{user_id}/activate')
async def activate_user(
        user_id: UUID,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Activate a user account

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    update_dto = SysSecUserUpdateDto(oid=user_id, active=True)
    updated_user = await SysSecUserRepository.update(db, update_dto, current_user_id)

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {"message": "User activated successfully"}


@sys_sec_user_router.post('/{user_id}/deactivate')
async def deactivate_user(
        user_id: UUID,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Deactivate a user account

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    update_dto = SysSecUserUpdateDto(oid=user_id, active=False)
    updated_user = await SysSecUserRepository.update(db, update_dto, current_user_id)

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {"message": "User deactivated successfully"}


@sys_sec_user_router.post('/{user_id}/unlock')
async def unlock_user(
        user_id: UUID,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Unlock a user account

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    user = await SysSecUserRepository.reset_failed_access(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {"message": "User unlocked successfully"}


@sys_sec_user_router.post('/{user_id}/change-password')
async def change_password(
        user_id: UUID,
        current_password: str,
        new_password: str,
        current_user_id: UUID = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """
    Change user password (requires current password)

    **Requires:**
    - Authentication: Bearer token
    - Users can only change their own password (or admins can change any)
    """
    # Check authorization - users can only change their own password
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change your own password"
        )

    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='New password must be at least 6 characters long'
        )

    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify current password
    if not verify_password(current_password, user.PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    update_dto = SysSecUserUpdateDto(
        oid=user_id,
        password=hash_password(new_password),
        change_password_on_first_logon=False
    )

    updated_user = await SysSecUserRepository.update(db, update_dto, user_id)

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating password"
        )

    return {"message": "Password changed successfully"}


@sys_sec_user_router.post('/{user_id}/admin-reset-password')
async def admin_reset_password(
        user_id: UUID,
        new_password: str,
        require_change_on_login: bool = True,
        current_user_id: UUID = Depends(get_current_user_id),
        _: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Admin endpoint to reset user password without requiring current password.
    This should be used by administrators only.

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role

    Args:
        user_id: ID of the user whose password will be reset
        new_password: The new password to set
        require_change_on_login: Whether user must change password on next login (default: True)
        current_user_id: ID of the admin performing the reset (from JWT/session)
    """
    if len(new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='New password must be at least 6 characters long'
        )

    # Validate target user exists
    user = SysSecUserRepository.fetch_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    try:
        # Hash the new password
        hashed_password = hash_password(new_password)

        # Update password and optionally set change_password_on_first_logon flag
        update_dto = SysSecUserUpdateDto(
            oid=user_id,
            password=hashed_password,
            change_password_on_first_logon=require_change_on_login,
            access_failed_count=0  # Reset failed login attempts
        )

        updated_user = await SysSecUserRepository.update(db, update_dto, current_user_id)

        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error resetting password"
            )

        return {
            "message": "Password reset successfully",
            "user_id": str(user_id),
            "username": updated_user.USERNAME,
            "require_change_on_login": require_change_on_login
        }

    except Exception as e:
        logger.exception('Error resetting user password')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error resetting password'
        )


@sys_sec_user_router.get('/stats/count')
def get_user_count(
        include_inactive: bool = Query(False),
        _: UUID = Depends(get_current_user_id),
        __: None = Depends(require_role('Administrator')),
        db: Session = Depends(get_db)
):
    """
    Get total user count

    **Requires:**
    - Authentication: Bearer token
    - Permission: Administrator role
    """
    count = SysSecUserRepository.count_users(db, include_inactive)
    return {
        "total_users": count,
        "include_inactive": include_inactive
    }


@sys_sec_user_router.post('/generate-password-hash')
async def generate_password_hash(request: PasswordHashRequest):
    """
    Generate bcrypt password hash for manual database recovery.

    **PUBLIC ENDPOINT** - No authentication required.

    **Use Case:**
    When system administrator loses password and needs to manually update
    the sys_sec_user.PASSWORD field in the database.

    **Security Notes:**
    - This endpoint is public because admin cannot authenticate if password is lost
    - Should only be accessible in secure environments (localhost/internal network)
    - All requests are logged for security audit trail
    - Generated hash can be directly inserted into sys_sec_user.PASSWORD field

    **Usage:**
    1. Call this endpoint with the new password to get the bcrypt hash
    2. Manually execute SQL to update the password:
       ```sql
       UPDATE sys_sec_user
       SET PASSWORD = '<generated_hash>'
       WHERE USERNAME = 'admin';
       ```
    3. Admin can now login with the new password

    **Example Request:**
    ```json
    {
        "password": "NewSecurePassword123"
    }
    ```

    **Example Response:**
    ```json
    {
        "password_hash": "$2b$12$...",
        "sql_example": "UPDATE sys_sec_user SET PASSWORD = '$2b$12$...' WHERE USERNAME = 'admin';",
        "note": "Copy the password_hash value and use it in the SQL UPDATE statement"
    }
    ```
    """
    # Log for security audit trail (without logging the actual password)
    logger.warning(
        "PUBLIC ENDPOINT ACCESSED: Password hash generation requested. "
        "This should only be used for administrator password recovery. "
        "Verify this request is legitimate."
    )

    try:
        # Generate bcrypt hash using the same function used for user creation
        hashed = hash_password(request.password)

        logger.info("Password hash generated successfully")

        return {
            "password_hash": hashed,
            "sql_example": f"UPDATE sys_sec_user SET PASSWORD = '{hashed}' WHERE USERNAME = 'admin';",
            "note": "Copy the password_hash value and use it in the SQL UPDATE statement to recover admin access"
        }

    except Exception as e:
        logger.exception("Error generating password hash")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating password hash"
        )