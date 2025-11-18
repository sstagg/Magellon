"""
Authentication Controller

Provides login, logout, token management, and system setup endpoints.
"""
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import app_settings
from database import get_db
from dependencies.auth import (
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from models.pydantic_models import SecuritySetupRequest
from models.security.security_models import RoleCreateDto
from repositories.security.sys_sec_user_repository import SysSecUserRepository
from repositories.security.sys_sec_role_repository import SysSecRoleRepository
from repositories.security.sys_sec_user_role_repository import SysSecUserRoleRepository
from services.casbin_policy_sync_service import CasbinPolicySyncService

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class LoginRequest(BaseModel):
    """Login request body"""
    username: str
    password: str

    class Config:
        json_schema_extra = {
            "example": {
                "username": "admin",
                "password": "password123"
            }
        }


class LoginResponse(BaseModel):
    """Login response"""
    access_token: str
    token_type: str
    user_id: str
    username: str
    expires_in: int  # minutes

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "user_id": "353aefbf-bd03-192d-6b46-efbfbdefbfbd",
                "username": "admin",
                "expires_in": 1440
            }
        }


class UserInfoResponse(BaseModel):
    """Current user information"""
    user_id: str
    username: str
    email: Optional[str]
    active: bool

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "353aefbf-bd03-192d-6b46-efbfbdefbfbd",
                "username": "admin",
                "email": "admin@magellon.com",
                "active": True
            }
        }


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login endpoint - authenticate user and return JWT token

    **Request Body:**
    - username: User's username
    - password: User's password

    **Response:**
    - access_token: JWT token for authentication
    - token_type: Always "bearer"
    - user_id: User's UUID
    - username: User's username
    - expires_in: Token expiration time in minutes

    **Usage:**
    ```bash
    curl -X POST http://localhost:8000/auth/login \\
      -H "Content-Type: application/json" \\
      -d '{"username": "admin", "password": "password123"}'
    ```

    **Save the token:**
    ```bash
    TOKEN=$(curl -X POST http://localhost:8000/auth/login \\
      -H "Content-Type: application/json" \\
      -d '{"username": "admin", "password": "password123"}' \\
      | jq -r '.access_token')
    ```

    **Use the token:**
    ```bash
    curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/protected-endpoint
    ```
    """
    logger.info(f"Login attempt for user: {login_data.username}")

    # Authenticate user
    user = SysSecUserRepository.authenticate_user(
        db,
        login_data.username,
        login_data.password
    )

    if not user:
        logger.warning(f"Failed login attempt for user: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.ACTIVE:
        logger.warning(f"Inactive user attempted login: {login_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.oid),
            "username": user.USERNAME
        },
        expires_delta=access_token_expires
    )

    logger.info(f"Successful login for user: {login_data.username} (ID: {user.oid})")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=str(user.oid),
        username=user.USERNAME,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint

    With JWT tokens, logout is typically handled client-side by deleting the token.
    The server cannot invalidate a JWT token before it expires.

    **Token Blacklisting (Optional):**
    If you need server-side logout, implement token blacklisting:
    1. Store logged-out tokens in Redis with expiration
    2. Check blacklist in authentication middleware
    3. Reject requests with blacklisted tokens

    **Client-side logout:**
    ```javascript
    // Delete token from localStorage
    localStorage.removeItem('access_token');

    // Or from cookies
    document.cookie = 'access_token=; Max-Age=0';
    ```

    **Response:**
    Returns success message. Client should delete the token.
    """
    return {
        "message": "Logged out successfully",
        "note": "Please delete the JWT token from client storage"
    }


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current authenticated user information

    **Headers:**
    - Authorization: Bearer <token>

    **Response:**
    Returns current user's information including user_id, username, email, and active status.

    **Usage:**
    ```bash
    curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/auth/me
    ```

    **Example Response:**
    ```json
    {
        "user_id": "353aefbf-bd03-192d-6b46-efbfbdefbfbd",
        "username": "admin",
        "email": "admin@magellon.com",
        "active": true
    }
    ```
    """
    return UserInfoResponse(
        user_id=str(current_user["user_id"]),
        username=current_user["username"],
        email=current_user.get("email"),
        active=current_user["active"]
    )


@router.post("/refresh")
async def refresh_token(
    current_user: dict = Depends(get_current_user)
):
    """
    Refresh JWT token

    Returns a new token with extended expiration time.
    Use this to keep users logged in without requiring re-authentication.

    **Headers:**
    - Authorization: Bearer <old_token>

    **Response:**
    Returns new JWT token with same user information but new expiration.

    **Usage:**
    ```bash
    curl -X POST -H "Authorization: Bearer $TOKEN" \\
      http://localhost:8000/auth/refresh
    ```

    **Best Practice:**
    Refresh token before it expires (e.g., when 80% of expiration time has passed).
    """
    # Create new token with same user data
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(current_user["user_id"]),
            "username": current_user["username"]
        },
        expires_delta=access_token_expires
    )

    logger.info(f"Token refreshed for user: {current_user['username']}")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=str(current_user["user_id"]),
        username=current_user["username"],
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES
    )


@router.post("/setup")
async def setup_security_system(
    request: SecuritySetupRequest,
    db: Session = Depends(get_db)
):
    """
    Bootstrap security system - Create admin user, Administrator role, and assign full permissions.

    **PUBLIC ENDPOINT** - No authentication required (used during initial installation).

    **Use Case:**
    - Initial application installation
    - Creating first administrator user
    - Setting up security system from scratch

    **Security:**
    - Can be disabled via `security_setup_settings.ENABLED` in config
    - Optional setup_token can be required for extra security
    - Idempotent - safe to run multiple times (won't duplicate data)

    **What it does:**
    1. Creates user if doesn't exist (hashes password with bcrypt)
    2. Creates "Administrator" role if doesn't exist (with full permissions)
    3. Assigns Administrator role to user if not already assigned
    4. Syncs permissions to Casbin authorization system

    **Request Body:**
    ```json
    {
        "username": "super",
        "password": "behd1d2",
        "setup_token": "optional_security_token"
    }
    ```

    **Response:**
    ```json
    {
        "message": "Security system setup completed successfully",
        "user_created": true,
        "role_created": false,
        "role_assigned": true,
        "user_id": "353aefbf-bd03-192d-6b46-efbfbdefbfbd",
        "username": "super",
        "role": "Administrator"
    }
    ```

    **Production Note:**
    Disable this endpoint after initial setup by setting `security_setup_settings.ENABLED: false` in production config.
    """
    logger.warning("SECURITY SETUP ENDPOINT ACCESSED - This should only be used during initial installation")

    # Check if setup is enabled
    if not app_settings.security_setup_settings.ENABLED:
        logger.error("Setup endpoint is disabled in configuration")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup endpoint is disabled. Enable it in configuration if needed."
        )

    # Verify setup token if configured
    if app_settings.security_setup_settings.SETUP_TOKEN:
        if not request.setup_token or request.setup_token != app_settings.security_setup_settings.SETUP_TOKEN:
            logger.warning(f"Invalid setup token provided for user: {request.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid setup token"
            )

    try:
        user_created = False
        role_created = False
        role_assigned = False

        # Step 1: Create user if doesn't exist
        existing_user = SysSecUserRepository.fetch_by_username(db, request.username)

        if existing_user:
            logger.info(f"User '{request.username}' already exists (ID: {existing_user.oid})")
            user = existing_user
        else:
            # Import hash_password from sys_sec_user_controller
            from controllers.security.sys_sec_user_controller import hash_password
            from models.pydantic_models import SysSecUserCreateDto

            logger.info(f"Creating new user: {request.username}")

            user_dto = SysSecUserCreateDto(
                username=request.username,
                password=hash_password(request.password),
                active=True,
                change_password_on_first_logon=False
            )

            user = await SysSecUserRepository.create(
                db=db,
                user_dto=user_dto,
                created_by=None  # No creator for bootstrap user
            )
            user_created = True
            logger.info(f"User created successfully: {request.username} (ID: {user.oid})")

        # Step 2: Create Administrator role if doesn't exist
        admin_role = SysSecRoleRepository.fetch_by_name(db, "Administrator")

        if admin_role:
            logger.info(f"Administrator role already exists (ID: {admin_role.Oid})")
        else:
            logger.info("Creating Administrator role")

            role_dto = RoleCreateDto(
                name="Administrator",
                is_administrative=True,
                can_edit_model=True,
                permission_policy=0  # Full permissions
            )

            admin_role = SysSecRoleRepository.create(db, role_dto)
            role_created = True
            logger.info(f"Administrator role created successfully (ID: {admin_role.Oid})")

        # Step 3: Assign Administrator role to user if not already assigned
        existing_assignment = SysSecUserRoleRepository.fetch_by_user_and_role(
            db, user.oid, admin_role.Oid
        )

        if existing_assignment:
            logger.info(f"User '{request.username}' already has Administrator role")
        else:
            logger.info(f"Assigning Administrator role to user: {request.username}")
            SysSecUserRoleRepository.assign_role_to_user(db, user.oid, admin_role.Oid)
            role_assigned = True
            logger.info(f"Administrator role assigned successfully to user: {request.username}")

        # Step 4: Sync permissions to Casbin
        logger.info("Syncing permissions to Casbin...")
        sync_service = CasbinPolicySyncService(db)
        sync_service.sync_all_policies()
        logger.info("Casbin permissions synchronized successfully")

        logger.info(f"Security setup completed for user: {request.username}")

        return {
            "message": "Security system setup completed successfully",
            "user_created": user_created,
            "role_created": role_created,
            "role_assigned": role_assigned,
            "user_id": str(user.oid),
            "username": user.USERNAME,
            "role": "Administrator",
            "note": "User has full administrative permissions. Disable setup endpoint in production config after installation."
        }

    except Exception as e:
        logger.exception(f"Error during security setup for user: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting up security system: {str(e)}"
        )
