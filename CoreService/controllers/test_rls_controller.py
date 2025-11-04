"""
Test Controller for Row-Level Security (RLS) Demonstration

This controller provides endpoints to test and demonstrate RLS functionality
with both SQLAlchemy ORM (automatic filtering) and raw SQL (manual filtering).

Includes permission management endpoints for easy testing without manual DB setup.

Usage:
    1. Get your user ID: GET /test-rls/whoami
    2. Grant yourself access: POST /test-rls/grant-access
    3. Test ORM filtering: GET /test-rls/images-orm
    4. Test SQL filtering: GET /test-rls/sessions-sql
    5. Clean up: DELETE /test-rls/revoke-access
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db
from models.sqlalchemy_models import (
    Image,
    Msession,
    SysSecUser,
    SysSecRole,
    SysSecTypePermission,
    SysSecObjectPermission
)

# RLS imports
from core.sqlalchemy_row_level_security import (
    get_filtered_db,
    get_session_filter_clause,
    check_session_access,
    get_accessible_sessions_for_user
)
from dependencies.auth import get_current_user_id
from services.casbin_service import CasbinService
from services.casbin_policy_sync_service import CasbinPolicySyncService

test_rls_router = APIRouter(prefix="/test-rls", tags=["RLS Testing"])


# ==================== Pydantic Models ====================

class ImageSummary(BaseModel):
    """Image summary for testing"""
    oid: UUID
    name: str
    session_id: UUID
    magnification: Optional[float] = None

    class Config:
        from_attributes = True


class SessionSummary(BaseModel):
    """Session summary for testing"""
    oid: UUID
    name: str
    description: Optional[str] = None


class GrantAccessRequest(BaseModel):
    """Request to grant session access"""
    session_id: UUID = Field(..., description="Session UUID to grant access to")
    read_access: bool = Field(True, description="Grant read permission")
    write_access: bool = Field(False, description="Grant write permission")
    delete_access: bool = Field(False, description="Grant delete permission")


class RevokeAccessRequest(BaseModel):
    """Request to revoke session access"""
    session_id: UUID = Field(..., description="Session UUID to revoke access from")


class AccessCheckResponse(BaseModel):
    """Response for access check"""
    session_id: UUID
    session_name: str
    can_read: bool
    can_write: bool
    can_delete: bool
    message: str


class WhoAmIResponse(BaseModel):
    """Response showing current user info"""
    user_id: UUID
    username: str
    roles: List[str]
    accessible_sessions: List[str]
    is_admin: bool


# ==================== Test Endpoints (Read Data) ====================

@test_rls_router.get('/images-orm', response_model=List[ImageSummary])
def test_images_with_orm(
    db: Session = Depends(get_filtered_db),  # ← Automatic RLS filtering!
    limit: int = Query(10, le=100, description="Max number of results")
):
    """
    Test RLS with SQLAlchemy ORM (Automatic Filtering).

    This endpoint uses `get_filtered_db` which automatically filters
    all queries to only return images from accessible sessions.

    **No manual filtering needed!**

    Example:
        GET /test-rls/images-orm?limit=5

    Returns:
        List of images from sessions you have access to
    """
    # This query is automatically filtered by RLS middleware!
    images = db.query(Image).filter(
        Image.GCRecord.is_(None)
    ).limit(limit).all()

    return [
        ImageSummary(
            oid=img.oid,
            name=img.name,
            session_id=img.session_id,
            magnification=img.magnification
        )
        for img in images
    ]


@test_rls_router.get('/sessions-sql', response_model=List[SessionSummary])
def test_sessions_with_sql(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),  # Get current user
    limit: int = Query(10, le=100, description="Max number of results")
):
    """
    Test RLS with Raw SQL (Manual Filtering).

    This endpoint uses raw SQL with `get_session_filter_clause()`
    to manually add RLS filtering to the query.

    **Demonstrates hybrid approach for existing raw SQL queries.**

    Example:
        GET /test-rls/sessions-sql?limit=5

    Returns:
        List of sessions you have access to
    """
    # Get RLS filter clause for manual filtering
    filter_clause, filter_params = get_session_filter_clause(
        user_id,
        column_name="oid"  # For msession table, filter by oid column
    )

    # Build raw SQL query with RLS filter
    query = text(f"""
        SELECT
            oid,
            name,
            description
        FROM msession
        WHERE GCRecord IS NULL
        {filter_clause}
        LIMIT :limit
    """)

    # Execute with merged parameters
    params = {"limit": limit, **filter_params}
    result = db.execute(query, params)
    rows = result.fetchall()

    return [
        SessionSummary(
            oid=row.oid,
            name=row.name,
            description=row.description
        )
        for row in rows
    ]


@test_rls_router.get('/check-access/{session_id}', response_model=AccessCheckResponse)
def check_access_to_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Check if you have access to a specific session.

    Tests the `check_session_access()` function.

    Example:
        GET /test-rls/check-access/123e4567-e89b-12d3-a456-426614174000

    Returns:
        Access permissions (read/write/delete) for the session
    """
    # Get session info
    session = db.query(Msession).filter(Msession.oid == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check access for each permission level
    can_read = check_session_access(user_id, session_id, action="read")
    can_write = check_session_access(user_id, session_id, action="write")
    can_delete = check_session_access(user_id, session_id, action="delete")

    # Build message
    if can_delete:
        message = "Full access (read/write/delete)"
    elif can_write:
        message = "Read and write access"
    elif can_read:
        message = "Read-only access"
    else:
        message = "No access"

    return AccessCheckResponse(
        session_id=session_id,
        session_name=session.name,
        can_read=can_read,
        can_write=can_write,
        can_delete=can_delete,
        message=message
    )


# ==================== Permission Management Endpoints ====================

@test_rls_router.post('/grant-access')
def grant_access_to_session(
    request: GrantAccessRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Grant yourself access to a specific session (for testing).

    This creates permissions in the database tables:
    - sys_sec_type_permission (type-level permission for Image/Msession)
    - sys_sec_object_permission (row-level permission with criteria)

    Then automatically syncs to Casbin.

    **Important**: In production, only admins should be able to grant access!
    This is a test endpoint for demonstration purposes.

    Example:
        POST /test-rls/grant-access
        {
            "session_id": "123e4567-e89b-12d3-a456-426614174000",
            "read_access": true,
            "write_access": false,
            "delete_access": false
        }

    Returns:
        Success message with details
    """
    # Verify session exists
    session = db.query(Msession).filter(Msession.oid == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get user's roles
    user_id_str = str(user_id)
    roles = CasbinService.get_roles_for_user(user_id_str)

    if not roles:
        raise HTTPException(
            status_code=400,
            detail="User has no roles assigned. Cannot grant permissions."
        )

    # Get the role from database
    role_name = roles[0]  # Use first role
    role_obj = db.query(SysSecRole).filter(SysSecRole.Name == role_name).first()
    if not role_obj:
        raise HTTPException(status_code=400, detail=f"Role '{role_name}' not found in database")

    # Create criteria expression for the session
    criteria = f"[session_id] = '{request.session_id}'"

    try:
        # Step 1: Get or create type permission for Image entity
        type_perm = db.query(SysSecTypePermission).filter(
            SysSecTypePermission.Role == role_obj.oid,
            SysSecTypePermission.TargetType == "Image"
        ).first()

        if not type_perm:
            # Create new type permission
            from uuid import uuid4
            type_perm = SysSecTypePermission(
                oid=uuid4(),
                Role=role_obj.oid,
                TargetType="Image",
                ReadState=1 if request.read_access else 0,
                WriteState=1 if request.write_access else 0,
                CreateState=0,
                DeleteState=1 if request.delete_access else 0,
                NavigateState=1 if request.read_access else 0
            )
            db.add(type_perm)
            db.flush()  # Get the ID

        # Step 2: Check if object permission already exists
        existing_obj_perm = db.query(SysSecObjectPermission).filter(
            SysSecObjectPermission.TypePermissionObject == type_perm.oid,
            SysSecObjectPermission.Criteria == criteria
        ).first()

        if existing_obj_perm:
            # Update existing permission
            existing_obj_perm.ReadState = 1 if request.read_access else 0
            existing_obj_perm.WriteState = 1 if request.write_access else 0
            existing_obj_perm.DeleteState = 1 if request.delete_access else 0
            existing_obj_perm.NavigateState = 1 if request.read_access else 0
            obj_perm = existing_obj_perm
            action = "Updated"
        else:
            # Create new object permission
            from uuid import uuid4
            obj_perm = SysSecObjectPermission(
                oid=uuid4(),
                TypePermissionObject=type_perm.oid,
                Criteria=criteria,
                ReadState=1 if request.read_access else 0,
                WriteState=1 if request.write_access else 0,
                DeleteState=1 if request.delete_access else 0,
                NavigateState=1 if request.read_access else 0
            )
            db.add(obj_perm)
            action = "Created"

        db.commit()

        # Step 3: Sync to Casbin
        policies_synced = CasbinPolicySyncService.sync_role_permissions(db, role_obj.oid)

        # Build response
        permissions_granted = []
        if request.read_access:
            permissions_granted.append("read")
        if request.write_access:
            permissions_granted.append("write")
        if request.delete_access:
            permissions_granted.append("delete")

        return {
            "success": True,
            "message": f"{action} permission for session '{session.name}'",
            "session_id": str(request.session_id),
            "session_name": session.name,
            "role": role_name,
            "permissions": permissions_granted,
            "criteria": criteria,
            "type_permission_id": str(type_perm.oid),
            "object_permission_id": str(obj_perm.oid),
            "policies_synced": policies_synced,
            "database_tables_updated": [
                "sys_sec_type_permission",
                "sys_sec_object_permission",
                "casbin_rule (via sync)"
            ]
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to grant access: {str(e)}"
        )


@test_rls_router.delete('/revoke-access')
def revoke_access_from_session(
    request: RevokeAccessRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Revoke your access to a specific session (cleanup after testing).

    This removes permissions from the database tables:
    - Deletes from sys_sec_object_permission
    - Automatically syncs to Casbin (removes from casbin_rule)

    Example:
        DELETE /test-rls/revoke-access
        {
            "session_id": "123e4567-e89b-12d3-a456-426614174000"
        }

    Returns:
        Success message with details
    """
    # Verify session exists
    session = db.query(Msession).filter(Msession.oid == request.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get user's roles
    user_id_str = str(user_id)
    roles = CasbinService.get_roles_for_user(user_id_str)

    if not roles:
        raise HTTPException(
            status_code=400,
            detail="User has no roles assigned."
        )

    try:
        # Build criteria to search for
        criteria = f"[session_id] = '{request.session_id}'"

        # Find all object permissions matching this criteria for user's roles
        permissions_deleted = []
        role_objs = db.query(SysSecRole).filter(SysSecRole.Name.in_(roles)).all()
        role_ids = [r.oid for r in role_objs]

        for role_id in role_ids:
            # Get type permissions for this role
            type_perms = db.query(SysSecTypePermission).filter(
                SysSecTypePermission.Role == role_id
            ).all()

            for type_perm in type_perms:
                # Find object permissions with matching criteria
                obj_perms = db.query(SysSecObjectPermission).filter(
                    SysSecObjectPermission.TypePermissionObject == type_perm.oid,
                    SysSecObjectPermission.Criteria == criteria
                ).all()

                for obj_perm in obj_perms:
                    permissions_deleted.append({
                        "permission_id": str(obj_perm.oid),
                        "type": type_perm.TargetType,
                        "criteria": obj_perm.Criteria
                    })
                    db.delete(obj_perm)

        if not permissions_deleted:
            return {
                "success": True,
                "message": f"No permissions found for session '{session.name}'",
                "session_id": str(request.session_id),
                "session_name": session.name,
                "criteria_searched": criteria
            }

        db.commit()

        # Sync to Casbin for each role
        policies_synced = 0
        for role_obj in role_objs:
            synced = CasbinPolicySyncService.sync_role_permissions(db, role_obj.oid)
            policies_synced += synced

        return {
            "success": True,
            "message": f"Revoked access to session '{session.name}'",
            "session_id": str(request.session_id),
            "session_name": session.name,
            "criteria": criteria,
            "permissions_deleted": len(permissions_deleted),
            "details": permissions_deleted,
            "policies_synced": policies_synced,
            "database_tables_updated": [
                "sys_sec_object_permission (deleted)",
                "casbin_rule (synced)"
            ]
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to revoke access: {str(e)}"
        )


# ==================== Helper/Info Endpoints ====================

@test_rls_router.get('/whoami', response_model=WhoAmIResponse)
def get_current_user_info(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Get information about the current authenticated user.

    Shows:
    - User ID and username
    - Assigned roles
    - List of accessible sessions
    - Whether user has admin privileges

    Example:
        GET /test-rls/whoami

    Returns:
        Current user information
    """
    # Get user from database
    user = db.query(SysSecUser).filter(SysSecUser.oid == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get roles
    user_id_str = str(user_id)
    roles = CasbinService.get_roles_for_user(user_id_str)

    # Get accessible sessions
    accessible_sessions = get_accessible_sessions_for_user(user_id)

    # Check if admin (has wildcard access)
    is_admin = '*' in accessible_sessions

    return WhoAmIResponse(
        user_id=user_id,
        username=user.USERNAME,
        roles=roles,
        accessible_sessions=accessible_sessions,
        is_admin=is_admin
    )


@test_rls_router.get('/sessions/all', response_model=List[SessionSummary])
def list_all_sessions(
    db: Session = Depends(get_db),
    limit: int = Query(20, le=100)
):
    """
    List ALL sessions in the database (no RLS filtering).

    Use this to see what sessions exist, then use `/test-rls/grant-access`
    to grant yourself access to specific ones for testing.

    **Note**: This endpoint intentionally bypasses RLS for testing purposes.
    In production, this should be admin-only!

    Example:
        GET /test-rls/sessions/all?limit=10

    Returns:
        List of all sessions (admin view)
    """
    sessions = db.query(Msession).filter(
        Msession.GCRecord.is_(None)
    ).limit(limit).all()

    return [
        SessionSummary(
            oid=s.oid,
            name=s.name,
            description=s.description
        )
        for s in sessions
    ]


@test_rls_router.get('/debug-info')
def get_debug_info(
    user_id: UUID = Depends(get_current_user_id)
):
    """
    Get detailed debug information about RLS for current user.

    Shows:
    - User ID
    - Assigned roles
    - All Casbin policies for user's roles
    - Accessible sessions
    - Total policy count

    Useful for troubleshooting permission issues.

    Example:
        GET /test-rls/debug-info
    """
    user_id_str = str(user_id)

    # Get roles
    roles = CasbinService.get_roles_for_user(user_id_str)

    # Get all policies
    all_policies = CasbinService.get_policy()

    # Filter policies for user's roles
    user_policies = [
        {
            "role": p[0],
            "resource": p[1],
            "action": p[2],
            "effect": p[3]
        }
        for p in all_policies
        if p[0] in roles
    ]

    # Get accessible sessions
    accessible_sessions = get_accessible_sessions_for_user(user_id)

    # Get filter clause info
    filter_clause, filter_params = get_session_filter_clause(UUID(user_id_str))

    return {
        "user_id": user_id_str,
        "roles": roles,
        "accessible_sessions": accessible_sessions,
        "is_admin": '*' in accessible_sessions,
        "total_policies": len(all_policies),
        "user_policies": user_policies,
        "user_policy_count": len(user_policies),
        "filter_clause": filter_clause,
        "filter_params": {
            k: list(v) if isinstance(v, tuple) else v
            for k, v in filter_params.items()
        }
    }


# ==================== Documentation Endpoint ====================

@test_rls_router.get('/')
def rls_test_guide():
    """
    Row-Level Security Test Guide

    Shows step-by-step instructions for testing RLS functionality.
    """
    return {
        "title": "Row-Level Security (RLS) Test Guide",
        "description": "Step-by-step guide to test RLS functionality",
        "steps": [
            {
                "step": 1,
                "title": "Get your user information",
                "endpoint": "GET /test-rls/whoami",
                "description": "Find out your user ID, roles, and current permissions"
            },
            {
                "step": 2,
                "title": "List all available sessions",
                "endpoint": "GET /test-rls/sessions/all",
                "description": "See all sessions in the database (pick one to test with)"
            },
            {
                "step": 3,
                "title": "Grant yourself access to a session",
                "endpoint": "POST /test-rls/grant-access",
                "body": {
                    "session_id": "<session-uuid-from-step-2>",
                    "read_access": True
                },
                "description": "Grant yourself read access to test session"
            },
            {
                "step": 4,
                "title": "Test ORM filtering (automatic)",
                "endpoint": "GET /test-rls/images-orm",
                "description": "See only images from sessions you have access to (automatic filtering)"
            },
            {
                "step": 5,
                "title": "Test SQL filtering (manual)",
                "endpoint": "GET /test-rls/sessions-sql",
                "description": "See only sessions you have access to (manual SQL filtering)"
            },
            {
                "step": 6,
                "title": "Check access to specific session",
                "endpoint": "GET /test-rls/check-access/{session_id}",
                "description": "Verify your permissions for a specific session"
            },
            {
                "step": 7,
                "title": "Clean up (revoke access)",
                "endpoint": "DELETE /test-rls/revoke-access",
                "body": {"session_id": "<session-uuid>"},
                "description": "Remove test permissions"
            },
            {
                "step": 8,
                "title": "Debug (if needed)",
                "endpoint": "GET /test-rls/debug-info",
                "description": "Get detailed debug information about your permissions"
            }
        ],
        "endpoints": {
            "read_endpoints": [
                "GET /test-rls/images-orm - Test ORM with automatic filtering",
                "GET /test-rls/sessions-sql - Test raw SQL with manual filtering",
                "GET /test-rls/check-access/{session_id} - Check access to specific session"
            ],
            "permission_management": [
                "POST /test-rls/grant-access - Grant yourself access (for testing)",
                "DELETE /test-rls/revoke-access - Revoke access (cleanup)"
            ],
            "helper_endpoints": [
                "GET /test-rls/whoami - Get current user info",
                "GET /test-rls/sessions/all - List all sessions",
                "GET /test-rls/debug-info - Debug permission issues"
            ]
        },
        "notes": [
            "All endpoints require authentication (JWT token)",
            "Grant/revoke endpoints are for testing only - in production, only admins should manage permissions",
            "ORM endpoint demonstrates automatic filtering (recommended for new code)",
            "SQL endpoint demonstrates manual filtering (for existing raw SQL queries)"
        ]
    }
