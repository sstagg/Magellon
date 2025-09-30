from enum import Enum

from pydantic import BaseModel, Field, Json, ValidationInfo, field_validator, ConfigDict
from typing import Any,Optional, List
import uuid
from uuid import UUID
from datetime import datetime



class SysSecUserDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    oid: Optional[UUID] = None
    omid: Optional[int] = None
    ouid: Optional[str] = Field(None, max_length=20)
    created_date: Optional[datetime] = None
    created_by: Optional[UUID] = None
    last_modified_date: Optional[datetime] = None
    last_modified_by: Optional[UUID] = None
    deleted_date: Optional[datetime] = None
    deleted_by: Optional[UUID] = None
    sync_status: Optional[int] = None
    version: Optional[str] = Field(None, max_length=10)
    password: Optional[str] = Field(None, alias="PASSWORD")
    change_password_on_first_logon: Optional[bool] = Field(None, alias="ChangePasswordOnFirstLogon")
    username: Optional[str] = Field(None, max_length=100, alias="USERNAME")
    active: Optional[bool] = Field(None, alias="ACTIVE")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")
    object_type: Optional[int] = Field(None, alias="ObjectType")
    access_failed_count: Optional[int] = Field(None, alias="AccessFailedCount")
    lockout_end: Optional[datetime] = Field(None, alias="LockoutEnd")


class SysSecUserCreateDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., max_length=100)
    password: str = Field(..., min_length=6)
    active: Optional[bool] = True
    change_password_on_first_logon: Optional[bool] = False
    omid: Optional[int] = None
    ouid: Optional[str] = Field(None, max_length=20)
    sync_status: Optional[int] = None
    version: Optional[str] = Field(None, max_length=10)
    object_type: Optional[int] = None


class SysSecUserUpdateDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    oid: UUID
    username: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=6)
    active: Optional[bool] = None
    change_password_on_first_logon: Optional[bool] = None
    omid: Optional[int] = None
    ouid: Optional[str] = Field(None, max_length=20)
    sync_status: Optional[int] = None
    version: Optional[str] = Field(None, max_length=10)
    object_type: Optional[int] = None
    access_failed_count: Optional[int] = None
    lockout_end: Optional[datetime] = None


class SysSecUserResponseDto(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    oid: UUID
    username: Optional[str] = Field(None, alias="USERNAME")
    active: Optional[bool] = Field(None, alias="ACTIVE")
    created_date: Optional[datetime] = None
    last_modified_date: Optional[datetime] = None
    omid: Optional[int] = None
    ouid: Optional[str] = None
    sync_status: Optional[int] = None
    version: Optional[str] = None
    change_password_on_first_logon: Optional[bool] = Field(None, alias="ChangePasswordOnFirstLogon")
    object_type: Optional[int] = Field(None, alias="ObjectType")
    access_failed_count: Optional[int] = Field(None, alias="AccessFailedCount")
    lockout_end: Optional[datetime] = Field(None, alias="LockoutEnd")




# ==================== ROLE MODELS ====================

class RoleBaseDto(BaseModel):
    """Base model for role"""
    name: str = Field(..., min_length=1, max_length=255, description="Role name")
    is_administrative: bool = Field(default=False, description="Is this an administrative role")
    can_edit_model: bool = Field(default=False, description="Can edit system models")
    permission_policy: int = Field(default=0, description="Permission policy type")
    tenant_id: Optional[UUID] = Field(None, description="Tenant ID for multi-tenancy")


class RoleCreateDto(RoleBaseDto):
    """Model for creating a new role"""
    pass


class RoleUpdateDto(BaseModel):
    """Model for updating a role"""
    oid: UUID = Field(..., description="Role ID")
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_administrative: Optional[bool] = None
    can_edit_model: Optional[bool] = None
    permission_policy: Optional[int] = None


class RoleResponseDto(RoleBaseDto):
    """Model for role response"""
    oid: UUID = Field(..., description="Role ID")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")
    object_type: Optional[int] = Field(None, alias="ObjectType")

    class Config:
        from_attributes = True
        populate_by_name = True


# ==================== USER-ROLE MODELS ====================

class UserRoleCreateDto(BaseModel):
    """Model for assigning a role to a user"""
    user_id: UUID = Field(..., description="User ID", alias="People")
    role_id: UUID = Field(..., description="Role ID", alias="Roles")

    class Config:
        populate_by_name = True


class UserRoleResponseDto(BaseModel):
    """Model for user-role relationship"""
    oid: UUID = Field(..., description="User-Role mapping ID", alias="OID")
    user_id: UUID = Field(..., description="User ID", alias="People")
    role_id: UUID = Field(..., description="Role ID", alias="Roles")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")

    class Config:
        from_attributes = True
        populate_by_name = True


class UserRoleDetailDto(BaseModel):
    """Detailed user-role information with role details"""
    oid: UUID
    user_id: UUID
    role_id: UUID
    role_name: str
    is_administrative: bool
    can_edit_model: bool


# ==================== PERMISSION MODELS ====================

class ActionPermissionBaseDto(BaseModel):
    """Base model for action permission"""
    action_id: str = Field(..., max_length=100, description="Action identifier")
    role_id: UUID = Field(..., description="Role ID", alias="Role")

    class Config:
        populate_by_name = True


class ActionPermissionCreateDto(ActionPermissionBaseDto):
    """Model for creating action permission"""
    pass


class ActionPermissionResponseDto(ActionPermissionBaseDto):
    """Model for action permission response"""
    oid: UUID = Field(..., description="Permission ID", alias="Oid")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")

    class Config:
        from_attributes = True
        populate_by_name = True


class NavigationPermissionBaseDto(BaseModel):
    """Base model for navigation permission"""
    item_path: str = Field(..., description="Navigation item path")
    navigate_state: int = Field(..., description="Navigation state (0=Deny, 1=Allow)")
    role_id: UUID = Field(..., description="Role ID", alias="Role")

    class Config:
        populate_by_name = True


class NavigationPermissionCreateDto(NavigationPermissionBaseDto):
    """Model for creating navigation permission"""
    pass


class NavigationPermissionResponseDto(NavigationPermissionBaseDto):
    """Model for navigation permission response"""
    oid: UUID = Field(..., description="Permission ID", alias="Oid")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")

    class Config:
        from_attributes = True
        populate_by_name = True


class ObjectPermissionBaseDto(BaseModel):
    """Base model for object permission"""
    type_permission_object: UUID = Field(..., description="Type permission object reference", alias="TypePermissionObject")
    read_state: int = Field(default=0, description="Read state (0=Deny, 1=Allow)")
    write_state: int = Field(default=0, description="Write state (0=Deny, 1=Allow)")
    delete_state: int = Field(default=0, description="Delete state (0=Deny, 1=Allow)")
    navigate_state: int = Field(default=0, description="Navigate state (0=Deny, 1=Allow)")
    criteria: Optional[str] = Field(None, description="Additional criteria for permission")

    class Config:
        populate_by_name = True


class ObjectPermissionCreateDto(ObjectPermissionBaseDto):
    """Model for creating object permission"""
    pass


class ObjectPermissionResponseDto(ObjectPermissionBaseDto):
    """Model for object permission response"""
    oid: UUID = Field(..., description="Permission ID", alias="Oid")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")

    class Config:
        from_attributes = True
        populate_by_name = True


class TypePermissionBaseDto(BaseModel):
    """Base model for type permission"""
    target_type: str = Field(..., description="Target type/class name")
    role: UUID = Field(..., description="Role ID", alias="Role")
    read_state: int = Field(default=0, description="Read state")
    write_state: int = Field(default=0, description="Write state")
    create_state: int = Field(default=0, description="Create state")
    delete_state: int = Field(default=0, description="Delete state")
    navigate_state: int = Field(default=0, description="Navigate state")

    class Config:
        populate_by_name = True


class TypePermissionCreateDto(TypePermissionBaseDto):
    """Model for creating type permission"""
    pass


class TypePermissionResponseDto(TypePermissionBaseDto):
    """Model for type permission response"""
    oid: UUID = Field(..., description="Permission ID", alias="Oid")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")

    class Config:
        from_attributes = True
        populate_by_name = True


class MemberPermissionBaseDto(BaseModel):
    """Base model for member permission"""
    members: str = Field(..., description="Member names (comma-separated)")
    read_state: int = Field(default=0, description="Read state")
    write_state: int = Field(default=0, description="Write state")
    criteria: Optional[str] = Field(None, description="Additional criteria")
    type_permission_object: UUID = Field(..., description="Type permission object reference", alias="TypePermissionObject")

    class Config:
        populate_by_name = True


class MemberPermissionCreateDto(MemberPermissionBaseDto):
    """Model for creating member permission"""
    pass


class MemberPermissionResponseDto(MemberPermissionBaseDto):
    """Model for member permission response"""
    oid: UUID = Field(..., description="Permission ID", alias="Oid")
    optimistic_lock_field: Optional[int] = Field(None, alias="OptimisticLockField")
    gc_record: Optional[int] = Field(None, alias="GCRecord")

    class Config:
        from_attributes = True
        populate_by_name = True


# ==================== COMPOSITE PERMISSION MODELS ====================

class PermissionCheckRequest(BaseModel):
    """Model for checking permissions"""
    user_id: UUID = Field(..., description="User ID to check permissions for")
    permission_type: str = Field(..., description="Type of permission (action/navigation/object/type)")
    resource: str = Field(..., description="Resource identifier")
    operation: Optional[str] = Field(None, description="Operation type (read/write/delete/etc)")


class PermissionCheckResponse(BaseModel):
    """Response for permission check"""
    has_permission: bool = Field(..., description="Whether user has the requested permission")
    reason: Optional[str] = Field(None, description="Reason if permission is denied")


class UserPermissionsSummaryDto(BaseModel):
    """Summary of all user permissions"""
    user_id: UUID
    username: str
    roles: List[RoleResponseDto]
    action_permissions: List[ActionPermissionResponseDto]
    navigation_permissions: List[NavigationPermissionResponseDto]
    is_admin: bool = Field(..., description="Whether user has any administrative role")


# ==================== BULK OPERATIONS ====================

class BulkRoleAssignmentDto(BaseModel):
    """Model for bulk role assignment to users"""
    user_ids: List[UUID] = Field(..., min_length=1, description="List of user IDs")
    role_id: UUID = Field(..., description="Role ID to assign")


class BulkPermissionCreateDto(BaseModel):
    """Model for bulk permission creation"""
    role_id: UUID = Field(..., description="Role ID")
    permissions: List[str] = Field(..., min_length=1, description="List of permission identifiers")
    permission_type: str = Field(..., description="Type of permission (action/navigation)")


class PermissionBatchResponseDto(BaseModel):
    """Response for batch permission operations"""
    created_count: int = Field(..., description="Number of permissions created")
    failed_count: int = Field(default=0, description="Number of failures")
    errors: Optional[List[str]] = Field(None, description="List of error messages")
