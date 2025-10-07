"""
JWT Authentication Dependencies

This module provides JWT-based authentication for the Magellon Core Service.

Usage:
    from dependencies.auth import get_current_user_id, get_current_user

    @router.get('/protected')
    def protected_route(user_id: UUID = Depends(get_current_user_id)):
        return {"user_id": user_id}
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from repositories.security.sys_sec_user_repository import SysSecUserRepository

import os
import logging

logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-CHANGE-THIS-IN-PRODUCTION-min-32-chars")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Security scheme
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token

    Args:
        data: Dictionary to encode in token (should include 'sub' with user_id)
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token string

    Example:
        token = create_access_token(
            data={"sub": str(user_id), "username": "admin"},
            expires_delta=timedelta(hours=24)
        )
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Decoded token payload dictionary

    Raises:
        HTTPException: 401 if token is invalid or expired

    Example:
        payload = decode_token(token)
        user_id = payload.get("sub")
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials - missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UUID:
    """
    Extract user ID from JWT token

    This is the main authentication dependency that replaces the placeholder
    in dependencies/permissions.py.

    Args:
        credentials: HTTP Bearer credentials from Authorization header

    Returns:
        User's UUID

    Raises:
        HTTPException: 401 if token invalid or user ID malformed

    Usage:
        @router.get('/protected')
        def protected_route(user_id: UUID = Depends(get_current_user_id)):
            return {"user_id": user_id}

        # Test with curl:
        # curl -H "Authorization: Bearer <token>" http://localhost:8000/protected
    """
    token = credentials.credentials
    payload = decode_token(token)
    user_id_str = payload.get("sub")

    try:
        user_uuid = UUID(user_id_str)
        return user_uuid
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"Invalid user ID in token: {user_id_str}, error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token"
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get full user object from database using JWT token

    This dependency both authenticates the token AND fetches the user from database.

    Args:
        credentials: HTTP Bearer credentials
        db: Database session

    Returns:
        Dictionary with user information:
        {
            "user_id": UUID,
            "username": str,
            "email": str,
            "active": bool
        }

    Raises:
        HTTPException: 401 if token invalid, user not found, or user inactive

    Usage:
        @router.get('/me')
        def get_current_user_info(
            current_user: dict = Depends(get_current_user)
        ):
            return current_user
    """
    token = credentials.credentials
    payload = decode_token(token)
    user_id_str = payload.get("sub")

    try:
        user_id = UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token"
        )

    # Fetch user from database
    user = SysSecUserRepository.fetch_by_id(db, user_id)

    if not user:
        logger.warning(f"User not found in database: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.ACTIVE:
        logger.warning(f"Inactive user attempted access: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled"
        )

    return {
        "user_id": user.oid,
        "username": user.USERNAME,
        "email": user.EMAIL if hasattr(user, 'EMAIL') else None,
        "active": user.ACTIVE
    }


def get_optional_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[UUID]:
    """
    Optional authentication - returns user ID if token present, None otherwise

    Use this for endpoints that work differently for authenticated vs anonymous users,
    but don't require authentication.

    Args:
        credentials: Optional HTTP Bearer credentials

    Returns:
        User UUID if authenticated, None if not

    Usage:
        @router.get('/items')
        def list_items(
            user_id: Optional[UUID] = Depends(get_optional_current_user_id),
            db: Session = Depends(get_db)
        ):
            if user_id:
                # Show all items for authenticated users
                return db.query(Item).all()
            else:
                # Show only public items for anonymous users
                return db.query(Item).filter(Item.is_public == True).all()
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        return UUID(user_id_str)
    except:
        # If token is invalid, treat as anonymous
        return None


# Export all authentication functions
__all__ = [
    'create_access_token',
    'decode_token',
    'get_current_user_id',
    'get_current_user',
    'get_optional_current_user_id',
    'SECRET_KEY',
    'ALGORITHM',
    'ACCESS_TOKEN_EXPIRE_MINUTES'
]
