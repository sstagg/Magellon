"""
Security Permissions Setup Script
=================================
This script sets up the security permissions in the database and syncs them to Casbin.

Run this script after initial database setup to ensure all permissions are properly configured.

Usage:
    python scripts/setup_security_permissions.py

What it does:
1. Creates Administrator and Users roles (if not exist)
2. Creates type permissions for msession and image
3. Syncs all permissions to Casbin
4. Verifies the setup

Author: Magellon Team
Date: 2025-12-09
"""

import sys
import os
from uuid import uuid4, UUID
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import session_local
from services.casbin_service import CasbinService


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_status(message: str, status: str = "info"):
    icons = {"ok": "[OK]", "error": "[ERROR]", "warn": "[WARN]", "info": "[INFO]"}
    print(f"  {icons.get(status, '')} {message}")


def get_or_create_role(db, role_name: str, is_administrative: bool = False):
    """Get existing role or create new one"""
    result = db.execute(
        text("SELECT Oid, Name FROM sys_sec_role WHERE Name = :name AND GCRecord IS NULL"),
        {"name": role_name}
    ).fetchone()

    if result:
        # Convert binary to UUID string
        role_id = UUID(bytes=result[0])
        print_status(f"Role '{role_name}' already exists: {role_id}", "ok")
        return role_id

    # Create new role
    role_id = uuid4()
    db.execute(
        text("""
            INSERT INTO sys_sec_role (Oid, Name, IsAdministrative, CanEditModel, PermissionPolicy, OptimisticLockField)
            VALUES (:oid, :name, :is_admin, 0, 0, 0)
        """),
        {
            "oid": role_id.bytes,
            "name": role_name,
            "is_admin": 1 if is_administrative else 0
        }
    )
    print_status(f"Created role '{role_name}': {role_id}", "ok")
    return role_id


def get_role_id_by_name(db, role_name: str) -> UUID:
    """Get role UUID by name"""
    result = db.execute(
        text("SELECT Oid FROM sys_sec_role WHERE Name = :name AND GCRecord IS NULL"),
        {"name": role_name}
    ).fetchone()

    if result:
        return UUID(bytes=result[0])
    return None


def create_type_permission_if_not_exists(db, role_id: UUID, target_type: str,
                                          read: int = 1, write: int = 1,
                                          create: int = 1, delete: int = 0,
                                          navigate: int = 1):
    """Create type permission if it doesn't exist"""
    # Check if exists
    result = db.execute(
        text("""
            SELECT Oid FROM sys_sec_type_permission
            WHERE Role = :role_id AND TargetType = :target_type AND GCRecord IS NULL
        """),
        {"role_id": role_id.bytes, "target_type": target_type}
    ).fetchone()

    if result:
        print_status(f"Type permission for '{target_type}' already exists", "ok")
        return UUID(bytes=result[0])

    # Create new
    perm_id = uuid4()
    db.execute(
        text("""
            INSERT INTO sys_sec_type_permission
            (Oid, Role, TargetType, ReadState, WriteState, CreateState, DeleteState, NavigateState, OptimisticLockField)
            VALUES (:oid, :role_id, :target_type, :read, :write, :create, :delete, :navigate, 0)
        """),
        {
            "oid": perm_id.bytes,
            "role_id": role_id.bytes,
            "target_type": target_type,
            "read": read,
            "write": write,
            "create": create,
            "delete": delete,
            "navigate": navigate
        }
    )
    print_status(f"Created type permission for '{target_type}'", "ok")
    return perm_id


def sync_permissions_to_casbin(db):
    """Sync all permissions from database to Casbin"""
    print_header("Syncing Permissions to Casbin")

    # Commit any pending transactions first
    db.commit()

    # Initialize Casbin
    CasbinService.initialize()

    # Clear existing policies using Casbin's adapter (not our db session)
    print_status("Clearing existing Casbin policies...")
    enforcer = CasbinService.get_enforcer()

    # Remove all policies through Casbin
    all_policies = enforcer.get_policy()
    for policy in all_policies:
        enforcer.remove_policy(*policy)

    all_groupings = enforcer.get_grouping_policy()
    for grouping in all_groupings:
        enforcer.remove_grouping_policy(*grouping)

    policies_added = 0

    # 1. Sync role assignments (g policies)
    print_status("Syncing role assignments...")
    user_roles = db.execute(text("""
        SELECT ur.People, r.Name
        FROM sys_sec_user_role ur
        JOIN sys_sec_role r ON ur.Roles = r.Oid
        WHERE r.GCRecord IS NULL
    """)).fetchall()

    for user_id_bytes, role_name in user_roles:
        user_id = str(UUID(bytes=user_id_bytes))
        CasbinService.add_role_for_user(user_id, role_name)
        policies_added += 1
        print_status(f"  g: {user_id[:8]}... -> {role_name}")

    # 2. Sync type permissions (p policies)
    print_status("Syncing type permissions...")
    type_perms = db.execute(text("""
        SELECT r.Name as RoleName, tp.TargetType, tp.ReadState, tp.WriteState,
               tp.CreateState, tp.DeleteState, tp.NavigateState
        FROM sys_sec_type_permission tp
        JOIN sys_sec_role r ON tp.Role = r.Oid
        WHERE tp.GCRecord IS NULL AND r.GCRecord IS NULL
        AND tp.TargetType IN ('msession', 'image', 'Msession', 'Image')
    """)).fetchall()

    for role_name, target_type, read, write, create, delete, navigate in type_perms:
        resource = f"{target_type.lower()}:*"

        if read == 1:
            CasbinService.add_permission_for_role(role_name, resource, "read", "allow")
            policies_added += 1
            print_status(f"  p: {role_name}, {resource}, read, allow")

        if write == 1:
            CasbinService.add_permission_for_role(role_name, resource, "write", "allow")
            policies_added += 1
            print_status(f"  p: {role_name}, {resource}, write, allow")

        if create == 1:
            CasbinService.add_permission_for_role(role_name, resource, "create", "allow")
            policies_added += 1
            print_status(f"  p: {role_name}, {resource}, create, allow")

        if navigate == 1:
            CasbinService.add_permission_for_role(role_name, resource, "navigate", "allow")
            policies_added += 1
            print_status(f"  p: {role_name}, {resource}, navigate, allow")

    # 3. Sync action permissions
    print_status("Syncing action permissions...")
    action_perms = db.execute(text("""
        SELECT r.Name as RoleName, ap.ActionId
        FROM sys_sec_action_permission ap
        JOIN sys_sec_role r ON ap.Role = r.Oid
        WHERE ap.GCRecord IS NULL AND r.GCRecord IS NULL
    """)).fetchall()

    for role_name, action_id in action_perms:
        resource = f"action:{action_id}"
        CasbinService.add_permission_for_role(role_name, resource, "execute", "allow")
        policies_added += 1
        print_status(f"  p: {role_name}, {resource}, execute, allow")

    # 4. Sync navigation permissions
    print_status("Syncing navigation permissions...")
    nav_perms = db.execute(text("""
        SELECT r.Name as RoleName, np.ItemPath, np.NavigateState
        FROM sys_sec_navigation_permission np
        JOIN sys_sec_role r ON np.Role = r.Oid
        WHERE np.GCRecord IS NULL AND r.GCRecord IS NULL
    """)).fetchall()

    for role_name, item_path, navigate_state in nav_perms:
        if navigate_state == 1:
            resource = f"navigation:{item_path}"
            CasbinService.add_permission_for_role(role_name, resource, "navigate", "allow")
            policies_added += 1
            print_status(f"  p: {role_name}, navigation:..., navigate, allow")

    print_status(f"Total policies synced: {policies_added}", "ok")
    return policies_added


def verify_setup(db):
    """Verify the security setup"""
    print_header("Verification")

    # Use fresh session for verification
    from database import session_local
    verify_db = session_local()

    # Check casbin_rule table
    result = verify_db.execute(text("SELECT COUNT(*) FROM casbin_rule")).fetchone()
    policy_count = result[0]
    print_status(f"Casbin policies in database: {policy_count}", "ok" if policy_count > 5 else "warn")

    # Check if Administrator has msession permissions
    result = verify_db.execute(text("""
        SELECT COUNT(*) FROM casbin_rule
        WHERE v0 = 'Administrator' AND v1 LIKE 'msession:%'
    """)).fetchone()
    msession_perms = result[0]
    print_status(f"Administrator msession permissions: {msession_perms}", "ok" if msession_perms >= 3 else "error")

    # Check if Administrator has image permissions
    result = verify_db.execute(text("""
        SELECT COUNT(*) FROM casbin_rule
        WHERE v0 = 'Administrator' AND v1 LIKE 'image:%'
    """)).fetchone()
    image_perms = result[0]
    print_status(f"Administrator image permissions: {image_perms}", "ok" if image_perms >= 3 else "error")

    # Test enforcement
    print_status("Testing Casbin enforcement...")
    CasbinService.initialize()

    # Get super user ID
    result = verify_db.execute(text("""
        SELECT oid FROM sys_sec_user WHERE USERNAME = 'super' AND GCRecord IS NULL
    """)).fetchone()

    if result:
        user_id = str(UUID(bytes=result[0]))

        # Test permissions
        tests = [
            ("msession:*", "read"),
            ("msession:*", "write"),
            ("image:*", "read"),
        ]

        all_passed = True
        for resource, action in tests:
            can_access = CasbinService.enforce(user_id, resource, action)
            status = "ok" if can_access else "error"
            print_status(f"  enforce(super, '{resource}', '{action}') = {can_access}", status)
            if not can_access:
                all_passed = False

        if all_passed:
            print_status("All enforcement tests PASSED!", "ok")
        else:
            print_status("Some enforcement tests FAILED!", "error")
    else:
        print_status("User 'super' not found - skipping enforcement tests", "warn")

    verify_db.close()
    return policy_count > 5


def main():
    print("\n" + "#" * 60)
    print("# MAGELLON SECURITY PERMISSIONS SETUP")
    print(f"# Time: {datetime.now()}")
    print("#" * 60)

    db = session_local()

    try:
        # Step 1: Ensure roles exist
        print_header("Step 1: Setting Up Roles")
        admin_role_id = get_or_create_role(db, "Administrator", is_administrative=True)
        users_role_id = get_or_create_role(db, "Users", is_administrative=False)
        db.commit()

        # Step 2: Ensure type permissions exist for Administrator
        print_header("Step 2: Setting Up Type Permissions")

        # Msession permissions for Administrator
        create_type_permission_if_not_exists(
            db, admin_role_id, "msession",
            read=1, write=1, create=1, delete=0, navigate=1
        )

        # Image permissions for Administrator
        create_type_permission_if_not_exists(
            db, admin_role_id, "image",
            read=1, write=1, create=1, delete=0, navigate=0
        )

        db.commit()

        # Step 3: Sync to Casbin
        sync_permissions_to_casbin(db)

        # Step 4: Verify
        success = verify_setup(db)

        # Summary
        print_header("SUMMARY")
        if success:
            print_status("Security permissions setup completed successfully!", "ok")
            print("\n  The 'super' user should now be able to:")
            print("    - Read, write, and create sessions (msession)")
            print("    - Read, write, and create images")
            print("    - Access the application")
        else:
            print_status("Setup completed but verification found issues.", "warn")
            print("\n  Please check the errors above and re-run if needed.")

    except Exception as e:
        print_status(f"Error: {str(e)}", "error")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
