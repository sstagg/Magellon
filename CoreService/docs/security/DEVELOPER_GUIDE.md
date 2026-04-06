# Magellon Security - Developer Guide

**Quick reference for building secure endpoints**

**Complete architecture:** See `SECURITY_ARCHITECTURE.md`

---

## Table of Contents

1. [Quick Start (30 Seconds)](#quick-start-30-seconds)
2. [Common Patterns](#common-patterns)
3. [Code Examples](#code-examples)
4. [Testing Guide](#testing-guide)
5. [Casbin Conditions Reference](#casbin-conditions-reference)
6. [RLS Implementation Guide](#rls-implementation-guide)
7. [Troubleshooting](#troubleshooting)
8. [FAQ](#faq)

---

## Quick Start (30 Seconds)

### Protect an Endpoint

```python
from dependencies.auth import get_current_user_id
from core.sqlalchemy_row_level_security import check_session_access
from uuid import UUID
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

@router.get('/images')
def get_images(
    session_name: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication
):
    """Get images for session - automatically filtered by user permissions."""

    # Get session
    msession = db.query(Msession).filter(Msession.name == session_name).first()
    if not msession:
        raise HTTPException(404, "Session not found")

    # ✅ Check access
    if not check_session_access(user_id, msession.oid, action="read"):
        raise HTTPException(403, "Access denied")

    # ✅ User has access - proceed
    images = db.query(Image).filter(Image.session_id == msession.oid).all()
    return images
```

**Done!** Your endpoint now has:
- ✅ JWT authentication
- ✅ Permission checking
- ✅ Session-based access control
- ✅ Audit logging

---

## Common Patterns

### Pattern 1: List Data (Most Common)

**Use Case:** Return list of resources filtered by user permissions

```python
from core.sqlalchemy_row_level_security import get_accessible_sessions_for_user
from dependencies.auth import get_current_user_id

@router.get('/sessions')
def get_sessions(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Return all sessions user can access."""

    # Get accessible session IDs
    accessible_ids = get_accessible_sessions_for_user(user_id)

    if accessible_ids == ['*']:
        # User has wildcard access - return all
        return db.query(Msession).filter(Msession.GCRecord.is_(None)).all()

    # Filter by accessible sessions
    return db.query(Msession).filter(
        Msession.oid.in_(accessible_ids),
        Msession.GCRecord.is_(None)
    ).all()
```

### Pattern 2: Get Single Resource

**Use Case:** Get specific resource by ID with permission check

```python
from core.sqlalchemy_row_level_security import check_session_access

@router.get('/images/{image_id}')
def get_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get specific image."""

    # Fetch image
    image = db.query(Image).filter(Image.oid == image_id).first()
    if not image:
        raise HTTPException(404, "Image not found")

    # ✅ Check session access
    if image.session_id:
        if not check_session_access(user_id, image.session_id, action="read"):
            raise HTTPException(403, "Access denied")

    return image
```

### Pattern 3: Create Resource

**Use Case:** Create new resource with write permission check

```python
from core.sqlalchemy_row_level_security import check_session_access

@router.post('/images')
def create_image(
    request: CreateImageRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Create new image in session."""

    # ✅ Check write access to session
    if not check_session_access(user_id, request.session_id, action="write"):
        raise HTTPException(403, "Access denied to session")

    # Create image
    image = Image(
        oid=uuid4(),
        name=request.name,
        session_id=request.session_id,
        # ... other fields
    )
    db.add(image)
    db.commit()
    db.refresh(image)

    return image
```

### Pattern 4: Update Resource

**Use Case:** Update resource with write permission

```python
@router.put('/images/{image_id}')
def update_image(
    image_id: UUID,
    request: UpdateImageRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Update image."""

    image = db.query(Image).filter(Image.oid == image_id).first()
    if not image:
        raise HTTPException(404, "Image not found")

    # ✅ Check write access
    if image.session_id:
        if not check_session_access(user_id, image.session_id, action="write"):
            raise HTTPException(403, "Access denied")

    # Update fields
    image.name = request.name
    # ... other updates

    db.commit()
    db.refresh(image)
    return image
```

### Pattern 5: Delete Resource

**Use Case:** Soft delete with delete permission

```python
@router.delete('/images/{image_id}')
def delete_image(
    image_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Soft delete image."""

    image = db.query(Image).filter(Image.oid == image_id).first()
    if not image:
        raise HTTPException(404, "Image not found")

    # ✅ Check delete access
    if image.session_id:
        if not check_session_access(user_id, image.session_id, action="delete"):
            raise HTTPException(403, "Access denied")

    # Soft delete
    image.GCRecord = 1
    db.commit()

    return {"deleted": True, "image_id": image_id}
```

### Pattern 6: Admin-Only Endpoint

**Use Case:** Endpoint accessible only to administrators

```python
from dependencies.permissions import require_role

@router.post('/admin/reset-database')
def reset_database(_: None = Depends(require_role('Administrator'))):
    """Reset database (admin only)."""

    # Only administrators can access this endpoint
    perform_database_reset()
    return {"status": "reset complete"}
```

### Pattern 7: Require Specific Permission

**Use Case:** Check specific Casbin permission

```python
from dependencies.permissions import require_permission

@router.get('/reports/financial')
def get_financial_report(
    _: None = Depends(require_permission('report', 'read_financial'))
):
    """Get financial report."""

    # User must have 'read_financial' action on 'report' resource
    return generate_financial_report()
```

### Pattern 8: Require System Action

**Use Case:** Check system action permission

```python
from dependencies.permissions import require_action

@router.post('/system/maintenance')
def system_maintenance(_: None = Depends(require_action('SystemMaintenance'))):
    """Perform system maintenance."""

    # User must have SystemMaintenance action permission
    perform_maintenance()
    return {"status": "maintenance complete"}
```

### Pattern 9: Optional Authentication

**Use Case:** Endpoint works for both authenticated and anonymous users

```python
from dependencies.auth import get_optional_current_user_id

@router.get('/images/public')
def get_public_images(
    db: Session = Depends(get_db),
    user_id: Optional[UUID] = Depends(get_optional_current_user_id)
):
    """Get public images, or all images if authenticated."""

    if user_id:
        # Authenticated - show all accessible images
        accessible_ids = get_accessible_sessions_for_user(user_id)
        return db.query(Image).filter(Image.session_id.in_(accessible_ids)).all()
    else:
        # Anonymous - show only public images
        return db.query(Image).filter(Image.is_public == True).all()
```

### Pattern 10: Check Permission in Code

**Use Case:** Conditional logic based on permissions

```python
from dependencies.permissions import check_permission

@router.get('/sessions/{session_id}/export')
def export_session(
    session_id: UUID,
    format: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Export session data."""

    # Check permission programmatically
    can_export = check_permission(user_id, f"msession:{session_id}", "export")

    if not can_export:
        raise HTTPException(403, "You don't have export permission")

    # Different export formats based on permissions
    if check_permission(user_id, "msession:*", "export_full"):
        return export_full_data(session_id, format)
    else:
        return export_summary_data(session_id, format)
```

---

## Code Examples

### Example 1: Complete Endpoint with All Security

```python
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from database import get_db
from dependencies.auth import get_current_user_id
from core.sqlalchemy_row_level_security import check_session_access
from models.sqlalchemy_models import Image, Msession
from models.pydantic_models import ImageDto

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get('/images', response_model=List[ImageDto])
def get_images(
    session_name: str,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication
):
    """
    Get images for a session with pagination.

    **Requires:** Authentication
    **Security:** User must have read access to the session
    **Returns:** Paginated list of images
    """
    # Log request
    logger.info(f"User {user_id} requesting images for session: {session_name}")

    # Get session
    msession = db.query(Msession).filter(
        Msession.name == session_name,
        Msession.GCRecord.is_(None)
    ).first()

    if not msession:
        logger.warning(f"Session not found: {session_name}")
        raise HTTPException(404, "Session not found")

    # ✅ Authorization check
    if not check_session_access(user_id, msession.oid, action="read"):
        logger.warning(
            f"SECURITY: User {user_id} denied access to session: {session_name}"
        )
        raise HTTPException(403, f"Access denied to session '{session_name}'")

    # Calculate pagination
    offset = (page - 1) * page_size

    # Query images
    images = db.query(Image).filter(
        Image.session_id == msession.oid,
        Image.GCRecord.is_(None)
    ).offset(offset).limit(page_size).all()

    # Count total
    total = db.query(Image).filter(
        Image.session_id == msession.oid,
        Image.GCRecord.is_(None)
    ).count()

    # Log success
    logger.info(
        f"User {user_id} accessed {len(images)} images from session: {session_name}"
    )

    # Return paginated response
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "images": [ImageDto.from_orm(img) for img in images]
    }
```

### Example 2: Grant Session Access (Admin Function)

```python
from pydantic import BaseModel

class GrantAccessRequest(BaseModel):
    user_id: UUID
    session_id: UUID
    read_access: bool = True
    write_access: bool = False
    delete_access: bool = False

@router.post('/admin/grant-session-access')
def grant_session_access(
    request: GrantAccessRequest,
    db: Session = Depends(get_db),
    admin_id: UUID = Depends(get_current_user_id),
    _: None = Depends(require_role('Administrator'))  # ✅ Admin only
):
    """
    Grant user access to specific session.

    **Requires:** Administrator role
    **Process:**
    1. Create sys_sec_object_permission entry
    2. Sync to Casbin
    3. User can now access session
    """
    from services.casbin_policy_sync_service import CasbinPolicySyncService
    from models.sqlalchemy_models import (
        SysSecTypePermission,
        SysSecObjectPermission,
        SysSecUserRole
    )

    logger.info(
        f"Admin {admin_id} granting access: "
        f"user={request.user_id}, session={request.session_id}"
    )

    # Validate session exists
    session = db.query(Msession).filter(
        Msession.oid == request.session_id,
        Msession.GCRecord.is_(None)
    ).first()

    if not session:
        raise HTTPException(404, "Session not found")

    # Get user's role
    user_role = db.query(SysSecUserRole).filter(
        SysSecUserRole.People == request.user_id
    ).first()

    if not user_role:
        raise HTTPException(400, "User has no role assigned")

    role_id = user_role.Roles

    # Get or create type permission for Image
    type_perm = db.query(SysSecTypePermission).filter(
        SysSecTypePermission.Role == role_id,
        SysSecTypePermission.TargetType == "Image",
        SysSecTypePermission.GCRecord.is_(None)
    ).first()

    if not type_perm:
        type_perm = SysSecTypePermission(
            Oid=uuid4(),
            Role=role_id,
            TargetType="Image",
            ReadState=1,
            WriteState=0,
            CreateState=0,
            DeleteState=0,
            NavigateState=1,
            GCRecord=None
        )
        db.add(type_perm)
        db.flush()

    # Create object permission
    criteria = f"[session_id] = '{request.session_id}'"
    obj_perm = SysSecObjectPermission(
        oid=uuid4(),
        TypePermissionObject=type_perm.Oid,
        Criteria=criteria,
        ReadState=1 if request.read_access else 0,
        WriteState=1 if request.write_access else 0,
        DeleteState=1 if request.delete_access else 0,
        NavigateState=1 if request.read_access else 0,
        GCRecord=None
    )
    db.add(obj_perm)
    db.commit()

    # Sync to Casbin
    stats = CasbinPolicySyncService.sync_all_policies(db, clear_existing=True)

    logger.info(
        f"Access granted successfully. Synced {stats['total_policies']} policies."
    )

    return {
        "success": True,
        "message": f"Access granted to session {session.name}",
        "policies_synced": stats['total_policies']
    }
```

### Example 3: Using Raw SQL with RLS

```python
from sqlalchemy import text
from core.sqlalchemy_row_level_security import get_session_filter_clause

@router.get('/images/stats')
def get_image_stats(
    session_name: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
):
    """Get image statistics for session."""

    msession = db.query(Msession).filter(Msession.name == session_name).first()
    if not msession:
        raise HTTPException(404, "Session not found")

    # ✅ Check access
    if not check_session_access(user_id, msession.oid, action="read"):
        raise HTTPException(403, "Access denied")

    # ✅ Get RLS filter clause
    filter_clause, filter_params = get_session_filter_clause(user_id)

    # Raw SQL query with RLS filtering
    query = text(f"""
        SELECT
            COUNT(*) as total_images,
            AVG(defocus) as avg_defocus,
            MIN(dose) as min_dose,
            MAX(dose) as max_dose
        FROM image
        WHERE session_id = :session_id
        AND GCRecord IS NULL
        {filter_clause}
    """)

    # Merge parameters
    params = {
        "session_id": msession.oid.bytes,
        **filter_params
    }

    result = db.execute(query, params).fetchone()

    return {
        "session_name": session_name,
        "total_images": result.total_images,
        "avg_defocus": float(result.avg_defocus) if result.avg_defocus else None,
        "min_dose": float(result.min_dose) if result.min_dose else None,
        "max_dose": float(result.max_dose) if result.max_dose else None
    }
```

---

## Testing Guide

### Testing with JWT Tokens

#### 1. Get a Token

```bash
# Login to get token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Response:
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "user_id": "60492044-efbf-bdef-bfbd-544fefbfbdef"
}
```

#### 2. Use Token in Requests

```bash
# Export token for convenience
export TOKEN="eyJhbGci..."

# Use token in requests
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/sessions

# Test permission denial
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/users
# Should return 403 if not admin
```

### Testing Permissions

#### Test Authentication (401)

```bash
# No token - should return 401
curl http://localhost:8000/api/sessions

# Invalid token - should return 401
curl -H "Authorization: Bearer invalid-token" \
  http://localhost:8000/api/sessions

# Expired token - should return 401
curl -H "Authorization: Bearer <expired-token>" \
  http://localhost:8000/api/sessions
```

#### Test Authorization (403)

```bash
# User without permission - should return 403
curl -H "Authorization: Bearer $USER_TOKEN" \
  http://localhost:8000/api/sessions/abc-123/delete

# User without role - should return 403
curl -H "Authorization: Bearer $USER_TOKEN" \
  http://localhost:8000/api/admin/cleanup
```

#### Test RLS Filtering

```python
# Test script: test_rls.py
import requests

# Login as user1
r1 = requests.post('http://localhost:8000/api/auth/login',
                   json={'username': 'user1', 'password': 'pass1'})
token1 = r1.json()['access_token']

# Login as user2
r2 = requests.post('http://localhost:8000/api/auth/login',
                   json={'username': 'user2', 'password': 'pass2'})
token2 = r2.json()['access_token']

# Get sessions as user1
sessions1 = requests.get(
    'http://localhost:8000/api/sessions',
    headers={'Authorization': f'Bearer {token1}'}
).json()

# Get sessions as user2
sessions2 = requests.get(
    'http://localhost:8000/api/sessions',
    headers={'Authorization': f'Bearer {token2}'}
).json()

# Verify users see different data
assert sessions1 != sessions2
print(f"User1 sees {len(sessions1)} sessions")
print(f"User2 sees {len(sessions2)} sessions")
```

### Unit Tests

```python
# tests/test_security.py
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_authentication_required():
    """Test endpoints require authentication."""
    response = client.get('/api/sessions')
    assert response.status_code == 401

def test_login_success():
    """Test successful login."""
    response = client.post('/api/auth/login', json={
        'username': 'admin',
        'password': 'admin123'
    })
    assert response.status_code == 200
    assert 'access_token' in response.json()

def test_permission_denied():
    """Test permission denial."""
    # Login as regular user
    login = client.post('/api/auth/login', json={
        'username': 'user',
        'password': 'userpass'
    })
    token = login.json()['access_token']

    # Try admin endpoint - should fail
    response = client.post('/api/admin/cleanup',
                          headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 403

def test_rls_filtering():
    """Test row-level security filtering."""
    # Login as user with limited access
    login = client.post('/api/auth/login', json={
        'username': 'jack',
        'password': 'jackpass'
    })
    token = login.json()['access_token']

    # Get sessions - should only see accessible ones
    response = client.get('/api/sessions',
                         headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200

    sessions = response.json()
    # Jack should not see all sessions
    assert len(sessions) < total_sessions_in_db
```

### Integration Tests

```python
# tests/test_security_integration.py
def test_full_workflow():
    """Test complete security workflow."""

    # 1. Create user
    user = create_test_user(username="testuser", password="testpass")

    # 2. Assign role
    role = create_test_role(name="Researcher")
    assign_role_to_user(user.oid, role.Oid)

    # 3. Grant session access
    session = create_test_session(name="test_session")
    grant_session_access(user.oid, session.oid, read_access=True)

    # 4. Sync policies
    CasbinPolicySyncService.sync_all_policies(db)

    # 5. Test access
    login = client.post('/api/auth/login', json={
        'username': 'testuser',
        'password': 'testpass'
    })
    token = login.json()['access_token']

    # Should be able to access session
    response = client.get(f'/api/sessions/{session.name}/images',
                         headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 200

    # Should NOT be able to access other session
    other_session = create_test_session(name="other_session")
    response = client.get(f'/api/sessions/{other_session.name}/images',
                         headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 403
```

---

## Casbin Conditions Reference

### Simple Equality

```sql
Criteria: "[session_id] = 'abc-123'"
```

**Result:** User can only access session with ID 'abc-123'

### IN Clause

```sql
Criteria: "[session_id] IN ('abc-123', 'def-456', 'ghi-789')"
```

**Result:** User can access these three specific sessions

### Dynamic User Context

```sql
Criteria: "[owner_id] = CurrentUserId()"
```

**Result:** User can only access resources they own

### OR Conditions

```sql
Criteria: "[is_public] = 1 OR [owner_id] = CurrentUserId()"
```

**Result:** User can access public resources OR resources they own

### Department-Based

```sql
Criteria: "[department_id] IN (SELECT department_id FROM user_departments WHERE user_id = CurrentUserId())"
```

**Result:** User can access resources from their departments

### Date-Based

```sql
Criteria: "[created_date] >= CurrentDate() - INTERVAL 30 DAY"
```

**Result:** User can only access resources created in last 30 days

### Complex Conditions

```sql
Criteria: "([owner_id] = CurrentUserId() OR [is_public] = 1) AND [status] = 'active'"
```

**Result:** User can access active resources that are public OR owned by them

### Supported Functions

- `CurrentUserId()` - Current user's UUID
- `CurrentDate()` - Current date
- `CurrentTime()` - Current timestamp
- Standard SQL functions (IN, NOT IN, AND, OR, etc.)

---

## RLS Implementation Guide

### Step 1: Understand Your Data Model

Identify the session relationship:

```
Msession (session table)
    ↓
Image.session_id → Msession.oid
Movie.session_id → Msession.oid
Particle.session_id → Msession.oid
```

### Step 2: Apply RLS Check

**Option A: Simple Check**
```python
if not check_session_access(user_id, session_id, "read"):
    raise HTTPException(403, "Access denied")
```

**Option B: Get Filter Clause**
```python
filter_clause, params = get_session_filter_clause(user_id)
# Use in raw SQL queries
```

**Option C: Get Accessible Sessions**
```python
accessible_ids = get_accessible_sessions_for_user(user_id)
# Filter ORM queries
query = query.filter(Model.session_id.in_(accessible_ids))
```

### Step 3: Add to Endpoint

```python
@router.get('/data')
def get_data(
    session_name: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # Step 1: Authenticate
):
    # Step 2: Get session
    session = db.query(Msession).filter(Msession.name == session_name).first()

    # Step 3: Check access
    if not check_session_access(user_id, session.oid, "read"):  # RLS check
        raise HTTPException(403, "Access denied")

    # Step 4: Query data (user has access)
    return db.query(Data).filter(Data.session_id == session.oid).all()
```

### Step 4: Test

```bash
# Test as authorized user
curl -H "Authorization: Bearer $AUTHORIZED_TOKEN" \
  http://localhost:8000/api/data?session_name=abc
# Should return data

# Test as unauthorized user
curl -H "Authorization: Bearer $UNAUTHORIZED_TOKEN" \
  http://localhost:8000/api/data?session_name=abc
# Should return 403
```

---

## Troubleshooting

### Common Issues

#### Issue: "Not authenticated" (401)

**Cause:** Missing or invalid JWT token

**Fix:**
```bash
# Get new token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your-username","password":"your-password"}'

# Use token
export TOKEN="<token-from-response>"
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/sessions
```

#### Issue: "Permission denied" (403)

**Cause:** User lacks required permission

**Fix:**
```python
# Grant access via admin endpoint
POST /api/session-access/grant
{
  "user_id": "user-uuid",
  "session_id": "session-uuid",
  "read_access": true
}

# OR sync Casbin policies
from services.casbin_policy_sync_service import CasbinPolicySyncService
CasbinPolicySyncService.sync_all_policies(db, clear_existing=True)
```

#### Issue: User sees no data

**Cause:** No permissions granted

**Fix:**
```python
# Check accessible sessions
from core.sqlalchemy_row_level_security import get_accessible_sessions_for_user
accessible = get_accessible_sessions_for_user(user_id)
print(f"User can access: {accessible}")

# If empty, grant access
# Use admin endpoint or database insert
```

#### Issue: Policies not updating

**Cause:** Casbin cache not synced

**Fix:**
```python
# Force reload
from services.casbin_service import CasbinService
CasbinService.reload_policy()

# OR full resync
CasbinPolicySyncService.sync_all_policies(db, clear_existing=True)
```

---

## FAQ

### Q: How do I add a new permission type?

**A:** Update the Casbin model and sync service:

1. Add column to appropriate `sys_sec_*` table
2. Update `CasbinPolicySyncService` to sync new permission type
3. Create FastAPI dependency in `dependencies/permissions.py`
4. Use dependency in endpoints

### Q: Can I check multiple permissions at once?

**A:** Yes, use `batch_enforce`:

```python
from services.casbin_service import CasbinService

requests = [
    (user_id, "msession:123", "read"),
    (user_id, "msession:123", "write"),
    (user_id, "msession:456", "read")
]

results = CasbinService.batch_enforce(requests)
# results = [True, False, True]
```

### Q: How do I test Casbin policies without database?

**A:** Use Casbin enforcer directly:

```python
from services.casbin_service import CasbinService

# Add test policy
CasbinService.add_role_for_user("test-user-id", "Researcher")
CasbinService.add_permission_for_role("Researcher", "msession:*", "read", "allow")

# Test
can_read = CasbinService.enforce("test-user-id", "msession:abc", "read")
assert can_read == True
```

### Q: How do I implement field-level permissions?

**A:** Use Pydantic models with conditional fields:

```python
class ImageResponse(BaseModel):
    oid: UUID
    name: str
    defocus: Optional[float] = None  # Only if has permission

def get_image_response(image, user_id):
    data = ImageResponse(oid=image.oid, name=image.name)

    # Add sensitive field if user has permission
    if check_permission(user_id, f"image:{image.oid}", "view_sensitive"):
        data.defocus = image.defocus

    return data
```

### Q: How do I log security events?

**A:** Use Python logging:

```python
import logging
logger = logging.getLogger(__name__)

# Log access
logger.info(f"User {user_id} accessed session {session_id}")

# Log denial
logger.warning(f"SECURITY: User {user_id} denied access to session {session_id}")

# Log suspicious activity
logger.error(f"SECURITY: Multiple failed login attempts for user {username}")
```

### Q: Can I have role hierarchy?

**A:** Yes, Casbin supports role inheritance:

```python
# Senior Researcher inherits from Researcher
CasbinService.add_role_for_user("SeniorResearcher", "Researcher")

# Grant permissions to base role
CasbinService.add_permission_for_role("Researcher", "msession:*", "read", "allow")

# Senior Researcher automatically gets Researcher permissions
```

---

## Quick Reference

### Essential Imports

```python
# Authentication
from dependencies.auth import get_current_user_id

# Authorization
from dependencies.permissions import (
    require_permission,
    require_role,
    require_action,
    check_permission
)

# RLS
from core.sqlalchemy_row_level_security import (
    check_session_access,
    get_session_filter_clause,
    get_accessible_sessions_for_user
)

# Casbin
from services.casbin_service import CasbinService
from services.casbin_policy_sync_service import CasbinPolicySyncService
```

### Common Functions

```python
# Check authentication
user_id: UUID = Depends(get_current_user_id)

# Check permission
if not check_permission(user_id, "msession:*", "read"):
    raise HTTPException(403)

# Check session access
if not check_session_access(user_id, session_id, "read"):
    raise HTTPException(403)

# Get accessible sessions
accessible = get_accessible_sessions_for_user(user_id)

# Sync Casbin policies
CasbinPolicySyncService.sync_all_policies(db)
```

---

**Document Version:** 3.0
**Last Updated:** 2025-11-18
**For Architecture Details:** See `SECURITY_ARCHITECTURE.md`

---

**END OF DOCUMENT**
