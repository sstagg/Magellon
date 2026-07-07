"""
Session Access Management Controller (Refined Approach)

Admin endpoints to grant/revoke session-specific permissions.
Uses Casbin as single source of truth.

Flow:
1. Admin grants session access → Writes to sys_sec_object_permission
2. Triggers Casbin sync → Updates Casbin policies
3. Endpoints use existing Casbin enforcement

Author: Magellon Development Team
Created: 2025-11-04 (Refined)
"""
from typing import List
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel, Field
import logging

from database import get_db
from dependencies.auth import get_current_user_id

from dependencies.permissions import require_role, check_permission
from services.casbin_service import CasbinService
from services.casbin_policy_sync_service import CasbinPolicySyncService
from services.security.criteria_parser_service import CasbinResourceBuilder
from models.sqlalchemy_models import (
    SysSecUserRole,
    SysSecTypePermission,
    SysSecObjectPermission,
    Msession,
    SysSecUser,
    SysSecRole
)

logger = logging.getLogger(__name__)

session_access_router = APIRouter(prefix='/api/session-access', tags=['Session Access'])


# ==================== REQUEST/RESPONSE MODELS ====================

class GrantSessionAccessRequest(BaseModel):
    """Request to grant session access to user."""
    user_id: UUID = Field(..., description="User ID to grant access to")
    session_id: UUID = Field(..., description="Session ID")
    read_access: bool = Field(True, description="Grant read permission")
    write_access: bool = Field(False, description="Grant write permission")
    delete_access: bool = Field(False, description="Grant delete permission")


class SessionAccessResponse(BaseModel):
    """Response for session access operations."""
    success: bool
    message: str
    permission_id: str = None
    policies_synced: int = 0


class SessionInfo(BaseModel):
    """Session information."""
    oid: str
    name: str
    description: str = None
    start_on: str = None
    user_can_access: bool = False


class AccessibleSessionsResponse(BaseModel):
    """Response with list of accessible sessions."""
    sessions: List[SessionInfo]
    count: int


# ==================== HELPER FUNCTIONS ====================

def _get_or_create_type_permission(
    db: Session,
    role_id: UUID,
    target_type: str = "Image"
) -> SysSecTypePermission:
    """Get existing type permission or create new one."""
    type_perm = db.query(SysSecTypePermission).filter(
        and_(
            SysSecTypePermission.Role == role_id,
            SysSecTypePermission.TargetType == target_type,
            SysSecTypePermission.GCRecord.is_(None)
        )
    ).first()

    if not type_perm:
        type_perm = SysSecTypePermission(
            Oid=uuid4(),
            Role=role_id,
            TargetType=target_type,
            ReadState=1,
            WriteState=0,
            CreateState=0,
            DeleteState=0,
            NavigateState=1,
            OptimisticLockField=0,
            GCRecord=None
        )
        db.add(type_perm)
        db.flush()
        logger.info(f"Created type permission for role {role_id}, type {target_type}")

    return type_perm


# ==================== ENDPOINTS ====================

@session_access_router.post('/grant', response_model=SessionAccessResponse)
async def grant_session_access(
    request: GrantSessionAccessRequest,
    db: Session = Depends(get_db),
    _: UUID = Depends(get_current_user_id),
    __: dict = Depends(require_role('Administrator'))
):
    """
    Grant user access to specific session.

    **Process:**
    1. Creates/updates entry in sys_sec_object_permission with Criteria
    2. Triggers Casbin sync to update policies
    3. User can now access the session via Casbin enforcement

    **Requires Administrator role**
    """
    try:
        # Validate session exists
        session = db.query(Msession).filter(
            and_(
                Msession.oid == request.session_id,
                Msession.GCRecord.is_(None)
            )
        ).first()

        if not session:
            raise HTTPException(
                status_code=404,
                detail="Session not found"
            )

        # Get user's role
        user_role = db.query(SysSecUserRole).filter(
            SysSecUserRole.People == request.user_id
        ).first()

        if not user_role:
            raise HTTPException(
                status_code=400,
                detail="User has no role assigned. Please assign a role first."
            )

        role_id = user_role.Roles

        # Get or create type permission for Image
        type_perm = _get_or_create_type_permission(db, role_id, "Image")

        # Check if object permission already exists
        criteria = f"[session_id] = '{request.session_id}'"
        existing = db.query(SysSecObjectPermission).filter(
            and_(
                SysSecObjectPermission.TypePermissionObject == type_perm.Oid,
                SysSecObjectPermission.Criteria == criteria,
                SysSecObjectPermission.GCRecord.is_(None)
            )
        ).first()

        if existing:
            # Update existing
            existing.ReadState = 1 if request.read_access else 0
            existing.WriteState = 1 if request.write_access else 0
            existing.DeleteState = 1 if request.delete_access else 0
            existing.NavigateState = 1 if request.read_access else 0
            existing.OptimisticLockField = (existing.OptimisticLockField or 0) + 1
            db.commit()

            permission_id = existing.oid
            message = "Session access updated"

        else:
            # Create new
            obj_perm = SysSecObjectPermission(
                oid=uuid4(),
                TypePermissionObject=type_perm.Oid,
                Criteria=criteria,
                ReadState=1 if request.read_access else 0,
                WriteState=1 if request.write_access else 0,
                DeleteState=1 if request.delete_access else 0,
                NavigateState=1 if request.read_access else 0,
                OptimisticLockField=0,
                GCRecord=None
            )
            db.add(obj_perm)
            db.commit()

            permission_id = obj_perm.oid
            message = "Session access granted"

        # Trigger Casbin sync for this specific role
        logger.info(f"Triggering Casbin sync for role {role_id}...")
        sync_stats = CasbinPolicySyncService.sync_role_permissions(db, role_id)
        policies_synced = sum(sync_stats.values())

        logger.info(f"Session access granted: user={request.user_id}, session={request.session_id}")

        return SessionAccessResponse(
            success=True,
            message=message,
            permission_id=str(permission_id),
            policies_synced=policies_synced
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error granting session access')
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f'Error granting access: {str(e)}'
        )


@session_access_router.post('/revoke', response_model=SessionAccessResponse)
async def revoke_session_access(
    user_id: UUID,
    session_id: UUID,
    db: Session = Depends(get_db),
    _: UUID = Depends(get_current_user_id),
    __: dict = Depends(require_role('Administrator'))
):
    """
    Revoke user's access to specific session.

    **Process:**
    1. Soft-deletes entry in sys_sec_object_permission
    2. Triggers Casbin sync to remove policies
    3. User can no longer access the session

    **Requires Administrator role**
    """
    try:
        # Get user's role
        user_role = db.query(SysSecUserRole).filter(
            SysSecUserRole.People == user_id
        ).first()

        if not user_role:
            raise HTTPException(
                status_code=400,
                detail="User has no role"
            )

        # Find type permission
        type_perm = db.query(SysSecTypePermission).filter(
            and_(
                SysSecTypePermission.Role == user_role.Roles,
                SysSecTypePermission.TargetType == 'Image',
                SysSecTypePermission.GCRecord.is_(None)
            )
        ).first()

        if not type_perm:
            raise HTTPException(
                status_code=404,
                detail="No permissions found for user"
            )

        # Find and soft-delete object permission
        criteria = f"[session_id] = '{session_id}'"
        obj_perm = db.query(SysSecObjectPermission).filter(
            and_(
                SysSecObjectPermission.TypePermissionObject == type_perm.Oid,
                SysSecObjectPermission.Criteria == criteria,
                SysSecObjectPermission.GCRecord.is_(None)
            )
        ).first()

        if not obj_perm:
            raise HTTPException(
                status_code=404,
                detail="Permission not found"
            )

        # Soft delete
        obj_perm.GCRecord = 1
        db.commit()

        # Trigger Casbin sync
        sync_stats = CasbinPolicySyncService.sync_role_permissions(db, user_role.Roles)
        policies_synced = sum(sync_stats.values())

        logger.info(f"Session access revoked: user={user_id}, session={session_id}")

        return SessionAccessResponse(
            success=True,
            message="Session access revoked",
            policies_synced=policies_synced
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error revoking session access')
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f'Error revoking access: {str(e)}'
        )


@session_access_router.get('/sessions/accessible', response_model=AccessibleSessionsResponse)
async def get_accessible_sessions(
    db: Session = Depends(get_db),
    current_user_id: UUID = Depends(get_current_user_id)
):
    """
    Get all sessions that current user can access via Casbin.

    Uses Casbin to check which sessions user has "read" permission for.

    **Authentication Required**
    """
    try:
        user_id_str = str(current_user_id)

        # Get all sessions
        sessions = db.query(Msession).filter(
            Msession.GCRecord.is_(None)
        ).order_by(Msession.start_on.desc()).all()

        accessible_sessions = []

        for session in sessions:
            # Build resource identifier
            resource = CasbinResourceBuilder.build_session_resource(session.oid)

            # Check if user can read this session via Casbin
            can_access = CasbinService.enforce(user_id_str, resource, "read")

            if can_access:
                accessible_sessions.append(SessionInfo(
                    oid=str(session.oid),
                    name=session.name or '',
                    description=session.description,
                    start_on=session.start_on.isoformat() if session.start_on else None,
                    user_can_access=True
                ))

        return AccessibleSessionsResponse(
            sessions=accessible_sessions,
            count=len(accessible_sessions)
        )

    except Exception as e:
        logger.exception('Error fetching accessible sessions')
        raise HTTPException(
            status_code=500,
            detail=f'Error fetching sessions: {str(e)}'
        )


@session_access_router.get('/check/{session_id}')
async def check_session_access(
    session_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id)
):
    """
    Check if current user can access specific session.

    Uses Casbin for enforcement.

    **Authentication Required**
    """
    try:
        user_id_str = str(current_user_id)
        resource = CasbinResourceBuilder.build_session_resource(session_id)

        can_read = CasbinService.enforce(user_id_str, resource, "read")
        can_write = CasbinService.enforce(user_id_str, resource, "write")
        can_delete = CasbinService.enforce(user_id_str, resource, "delete")

        # Get user's roles
        roles = CasbinService.get_roles_for_user(user_id_str)

        return {
            "session_id": str(session_id),
            "user_id": str(current_user_id),
            "can_read": can_read,
            "can_write": can_write,
            "can_delete": can_delete,
            "roles": roles,
            "resource": resource
        }

    except Exception as e:
        logger.exception('Error checking session access')
        raise HTTPException(
            status_code=500,
            detail=f'Error checking access: {str(e)}'
        )


@session_access_router.get('/session/{session_id}/users')
async def get_session_users(
    session_id: UUID,
    db: Session = Depends(get_db),
    _: UUID = Depends(get_current_user_id),
    __: dict = Depends(require_role('Administrator'))
):
    """
    Get all users who have access to specific session.

    **Requires Administrator role**
    """
    try:
        # Find all object permissions for this session
        criteria_pattern = f"%{session_id}%"
        object_perms = db.query(SysSecObjectPermission).filter(
            and_(
                SysSecObjectPermission.Criteria.like(criteria_pattern),
                SysSecObjectPermission.GCRecord.is_(None)
            )
        ).all()

        users_with_access = []

        for obj_perm in object_perms:
            # Get type permission
            type_perm = db.query(SysSecTypePermission).filter(
                SysSecTypePermission.Oid == obj_perm.TypePermissionObject
            ).first()

            if not type_perm:
                continue

            # Get role
            role = db.query(SysSecRole).filter(
                and_(
                    SysSecRole.Oid == type_perm.Role,
                    SysSecRole.GCRecord.is_(None)
                )
            ).first()

            if not role:
                continue

            # Get users with this role
            user_roles = db.query(SysSecUserRole).filter(
                SysSecUserRole.Roles == role.Oid
            ).all()

            for ur in user_roles:
                user = db.query(SysSecUser).filter(
                    SysSecUser.oid == ur.People
                ).first()

                if user:
                    users_with_access.append({
                        "user_id": str(user.oid),
                        "username": user.USERNAME,
                        "role_name": role.Name,
                        "read_access": bool(obj_perm.ReadState),
                        "write_access": bool(obj_perm.WriteState),
                        "delete_access": bool(obj_perm.DeleteState),
                        "permission_id": str(obj_perm.oid)
                    })

        return {
            "session_id": str(session_id),
            "users": users_with_access,
            "count": len(users_with_access)
        }

    except Exception as e:
        logger.exception('Error fetching session users')
        raise HTTPException(
            status_code=500,
            detail=f'Error fetching users: {str(e)}'
        )
