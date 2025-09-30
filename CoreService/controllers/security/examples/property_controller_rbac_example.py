"""
Example Property Controller with RBAC Integration

This file demonstrates how to use the RBAC system in a real-world controller
with different permission levels for different operations.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
from dependencies.auth_dependencies import (
    require_authenticated_user,
    require_admin_user,
    require_role,
    require_any_role,
    require_type_permission,
    assert_user_permission
)
from services.authorization_service import AuthorizationService

import logging

logger = logging.getLogger(__name__)

# Create router
example_property_router = APIRouter(prefix="/api/properties", tags=["Properties - Example"])


# ==================== PUBLIC ENDPOINTS (No Auth Required) ====================

@example_property_router.get("/public", summary="Public property listings")
async def get_public_properties(
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db)
):
    """
    Get public property listings - no authentication required
    """
    # Your property fetching logic here
    return {
        "properties": [],
        "message": "Public property listings"
    }


# ==================== AUTHENTICATED ENDPOINTS ====================

@example_property_router.get("/my-properties", summary="Get user's properties")
async def get_my_properties(
    user_id: UUID = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Get properties owned by the authenticated user
    Requires: Authenticated user
    """
    # Fetch properties owned by this user
    return {
        "user_id": str(user_id),
        "properties": [],
        "message": "User's properties"
    }


# ==================== ROLE-BASED ENDPOINTS ====================

@example_property_router.get("/listings", summary="View all property listings")
async def get_all_property_listings(
    user_id: UUID = Depends(require_type_permission("Property", "read")),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    """
    Get all property listings
    Requires: Read permission on Property type
    """
    # Fetch all properties based on user's permissions
    return {
        "properties": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }


@example_property_router.get("/{property_id}", summary="Get property details")
async def get_property(
    property_id: UUID,
    user_id: UUID = Depends(require_type_permission("Property", "read")),
    db: Session = Depends(get_db)
):
    """
    Get detailed property information
    Requires: Read permission on Property type
    """
    # Check if user has permission to view this specific property
    # You might want additional business logic here
    
    return {
        "property_id": str(property_id),
        "details": {},
        "message": "Property details"
    }


@example_property_router.post("/", summary="Create new property", status_code=201)
async def create_property(
    property_data: dict,  # Replace with actual PropertyCreateDto
    user_id: UUID = Depends(require_type_permission("Property", "create")),
    db: Session = Depends(get_db)
):
    """
    Create a new property
    Requires: Create permission on Property type
    """
    # Property creation logic
    return {
        "property_id": "new-property-id",
        "created_by": str(user_id),
        "message": "Property created successfully"
    }


@example_property_router.put("/{property_id}", summary="Update property")
async def update_property(
    property_id: UUID,
    property_data: dict,  # Replace with actual PropertyUpdateDto
    user_id: UUID = Depends(require_type_permission("Property", "write")),
    db: Session = Depends(get_db)
):
    """
    Update an existing property
    Requires: Write permission on Property type
    """
    # Check ownership or additional permissions
    # Property update logic
    return {
        "property_id": str(property_id),
        "updated_by": str(user_id),
        "message": "Property updated successfully"
    }


@example_property_router.delete("/{property_id}", summary="Delete property")
async def delete_property(
    property_id: UUID,
    user_id: UUID = Depends(require_type_permission("Property", "delete")),
    db: Session = Depends(get_db)
):
    """
    Delete a property
    Requires: Delete permission on Property type
    """
    # Property deletion logic
    return {
        "property_id": str(property_id),
        "deleted_by": str(user_id),
        "message": "Property deleted successfully"
    }


# ==================== SPECIFIC ROLE ENDPOINTS ====================

@example_property_router.post("/{property_id}/approve", summary="Approve property listing")
async def approve_property(
    property_id: UUID,
    user_id: UUID = Depends(require_role("Manager")),
    db: Session = Depends(get_db)
):
    """
    Approve a property for public listing
    Requires: Manager role
    """
    # Approval logic
    return {
        "property_id": str(property_id),
        "approved_by": str(user_id),
        "message": "Property approved"
    }


@example_property_router.post("/{property_id}/feature", summary="Feature property on homepage")
async def feature_property(
    property_id: UUID,
    user_id: UUID = Depends(require_any_role(["Manager", "Administrator"])),
    db: Session = Depends(get_db)
):
    """
    Feature a property on the homepage
    Requires: Manager or Administrator role
    """
    # Feature logic
    return {
        "property_id": str(property_id),
        "featured_by": str(user_id),
        "message": "Property featured"
    }


# ==================== ADMIN-ONLY ENDPOINTS ====================

@example_property_router.get("/admin/all", summary="Admin view all properties")
async def admin_get_all_properties(
    user_id: UUID = Depends(require_admin_user),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Admin endpoint to view all properties including deleted ones
    Requires: Administrator role
    """
    return {
        "properties": [],
        "include_deleted": include_deleted,
        "total": 0,
        "message": "Admin property list"
    }


@example_property_router.post("/{property_id}/restore", summary="Restore deleted property")
async def restore_property(
    property_id: UUID,
    user_id: UUID = Depends(require_admin_user),
    db: Session = Depends(get_db)
):
    """
    Restore a soft-deleted property
    Requires: Administrator role
    """
    return {
        "property_id": str(property_id),
        "restored_by": str(user_id),
        "message": "Property restored"
    }


# ==================== COMPLEX PERMISSION LOGIC ====================

@example_property_router.post("/{property_id}/publish", summary="Publish property")
async def publish_property(
    property_id: UUID,
    user_id: UUID = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Publish a property listing
    Complex permission logic:
    - Property owner can publish their own properties
    - Manager role can publish any property
    - Must have 'PublishProperty' action permission
    """
    # Check if user has the publish action permission
    has_publish_permission = AuthorizationService.user_has_action_permission(
        db, user_id, "PublishProperty"
    )
    
    if not has_publish_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to publish properties"
        )
    
    # Check if user is the owner or a manager
    is_manager = AuthorizationService.user_has_role(db, user_id, "Manager")
    is_admin = AuthorizationService.user_is_admin(db, user_id)
    
    # TODO: Check if user is the property owner
    # is_owner = check_property_ownership(db, property_id, user_id)
    is_owner = False  # Placeholder
    
    if not (is_owner or is_manager or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only publish your own properties unless you're a manager"
        )
    
    # Publish logic
    return {
        "property_id": str(property_id),
        "published_by": str(user_id),
        "message": "Property published successfully"
    }


@example_property_router.put("/{property_id}/pricing", summary="Update property pricing")
async def update_property_pricing(
    property_id: UUID,
    pricing_data: dict,  # Replace with actual PricingUpdateDto
    user_id: UUID = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Update property pricing
    Complex permission logic:
    - Requires write permission on Property type
    - Or requires 'ManagePricing' action permission
    - Or must be property owner
    """
    # Check if user has general write permission
    has_write_permission = AuthorizationService.user_has_type_permission(
        db, user_id, "Property", "write"
    )
    
    # Check if user has specific pricing management permission
    has_pricing_permission = AuthorizationService.user_has_action_permission(
        db, user_id, "ManagePricing"
    )
    
    # TODO: Check property ownership
    # is_owner = check_property_ownership(db, property_id, user_id)
    is_owner = False  # Placeholder
    
    if not (has_write_permission or has_pricing_permission or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update property pricing"
        )
    
    # Pricing update logic
    return {
        "property_id": str(property_id),
        "updated_by": str(user_id),
        "message": "Pricing updated successfully"
    }


@example_property_router.get("/{property_id}/analytics", summary="Get property analytics")
async def get_property_analytics(
    property_id: UUID,
    user_id: UUID = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Get analytics for a property
    Requires: ViewAnalytics action permission OR property ownership
    """
    # Use manual permission assertion
    has_analytics_permission = AuthorizationService.user_has_action_permission(
        db, user_id, "ViewAnalytics"
    )
    
    # TODO: Check property ownership
    # is_owner = check_property_ownership(db, property_id, user_id)
    is_owner = False  # Placeholder
    
    if not (has_analytics_permission or is_owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view analytics for this property"
        )
    
    # Return analytics data
    return {
        "property_id": str(property_id),
        "analytics": {
            "views": 1250,
            "inquiries": 45,
            "favorites": 87
        }
    }


# ==================== UTILITY ENDPOINTS ====================

@example_property_router.get("/user/{user_id}/permissions", summary="Get user's property permissions")
async def get_user_property_permissions(
    user_id: UUID,
    current_user_id: UUID = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Get what property-related permissions a user has
    Note: Users can only check their own permissions unless they're an admin
    """
    # Users can only check their own permissions
    is_admin = AuthorizationService.user_is_admin(db, current_user_id)
    if str(user_id) != str(current_user_id) and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only check your own permissions"
        )
    
    # Get permission summary
    permissions = {
        "can_read": AuthorizationService.user_has_type_permission(db, user_id, "Property", "read"),
        "can_create": AuthorizationService.user_has_type_permission(db, user_id, "Property", "create"),
        "can_update": AuthorizationService.user_has_type_permission(db, user_id, "Property", "write"),
        "can_delete": AuthorizationService.user_has_type_permission(db, user_id, "Property", "delete"),
        "can_publish": AuthorizationService.user_has_action_permission(db, user_id, "PublishProperty"),
        "can_approve": AuthorizationService.user_has_role(db, user_id, "Manager") or 
                      AuthorizationService.user_is_admin(db, user_id),
        "can_view_analytics": AuthorizationService.user_has_action_permission(db, user_id, "ViewAnalytics"),
        "is_admin": AuthorizationService.user_is_admin(db, user_id),
        "roles": [role['role_name'] for role in AuthorizationService.get_user_roles(db, user_id)]
    }
    
    return {
        "user_id": str(user_id),
        "permissions": permissions
    }


# ==================== USAGE NOTES ====================
"""
RBAC Integration Patterns Demonstrated:

1. PUBLIC ENDPOINTS: No authentication required
   - Use for completely public data

2. AUTHENTICATED ONLY: require_authenticated_user
   - Use when you just need to know who the user is

3. TYPE PERMISSIONS: require_type_permission("Type", "operation")
   - Use for standard CRUD operations on entity types
   - Operations: read, write, create, delete, navigate

4. ROLE REQUIREMENTS: require_role("RoleName")
   - Use when specific role is required
   - Good for business-specific operations

5. MULTIPLE ROLES: require_any_role(["Role1", "Role2"])
   - Use when any of several roles can perform the action

6. ADMIN ONLY: require_admin_user
   - Use for system administration tasks

7. COMPLEX LOGIC: Manual checks with AuthorizationService
   - Use when you need OR/AND logic
   - Use when you need to combine ownership with roles
   - Use when you need conditional permissions

8. PERMISSION CHECKING: Use for readonly checks (like showing/hiding UI elements)
   - AuthorizationService.user_has_*
   - Don't throw exceptions, just return boolean

To register this router in your main.py:
```python
from controllers.examples.property_controller_rbac_example import example_property_router

app.include_router(example_property_router)
```
"""
