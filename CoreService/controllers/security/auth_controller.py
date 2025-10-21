"""
Authentication Controller

Provides login, logout, and token management endpoints.
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies.auth import (
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from repositories.security.sys_sec_user_repository import SysSecUserRepository

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
