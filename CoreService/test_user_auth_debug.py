"""
Test script to debug authentication issues for a user.
This script checks:
1. User exists in database and is active
2. Password verification
3. Database roles (sys_sec_user_role table)
4. Casbin roles and permissions
5. JWT token generation and validation

Usage:
    python test_user_auth_debug.py <username> <password>

Example:
    python test_user_auth_debug.py super mypassword
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
from datetime import datetime
from uuid import UUID

# Import application modules
from config import app_settings
from models.sqlalchemy_models import SysSecUser, SysSecRole, SysSecUserRole
from services.casbin_service import CasbinService
from dependencies.auth import create_access_token, decode_token, SECRET_KEY, ALGORITHM

# Password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_db_session():
    """Create database session"""
    db_settings = app_settings.database_settings
    db_url = f"{db_settings.DB_Driver}://{db_settings.DB_USER}:{db_settings.DB_PASSWORD}@{db_settings.DB_HOST}:{db_settings.DB_Port}/{db_settings.DB_NAME}"
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(label: str, value, status: str = None):
    """Print formatted result"""
    status_icon = ""
    if status == "ok":
        status_icon = "[OK] "
    elif status == "error":
        status_icon = "[ERROR] "
    elif status == "warn":
        status_icon = "[WARN] "
    print(f"  {status_icon}{label}: {value}")


def check_user_in_database(db, username: str):
    """Check if user exists in database"""
    print_header("1. DATABASE USER CHECK")

    # Query user
    user = db.query(SysSecUser).filter(SysSecUser.USERNAME == username).first()

    if not user:
        print_result("User found", "NO - User does not exist in database", "error")
        return None

    print_result("User found", "YES", "ok")
    print_result("User OID (UUID)", str(user.oid))
    print_result("Username", user.USERNAME)
    print_result("Active", user.ACTIVE, "ok" if user.ACTIVE else "error")
    print_result("GCRecord (soft delete)", user.GCRecord, "ok" if user.GCRecord is None else "error")
    print_result("Password hash exists", "YES" if user.PASSWORD else "NO", "ok" if user.PASSWORD else "error")
    print_result("Password hash length", len(user.PASSWORD) if user.PASSWORD else 0)
    print_result("Password hash preview", user.PASSWORD[:50] + "..." if user.PASSWORD and len(user.PASSWORD) > 50 else user.PASSWORD)
    print_result("Lockout End", user.LockoutEnd)
    print_result("Access Failed Count", user.AccessFailedCount)
    print_result("Created Date", user.created_date)

    # Check if locked out
    if user.LockoutEnd and user.LockoutEnd > datetime.now():
        print_result("Account Status", f"LOCKED until {user.LockoutEnd}", "error")
    else:
        print_result("Account Status", "Not locked", "ok")

    return user


def check_password(user: SysSecUser, password: str):
    """Verify password"""
    print_header("2. PASSWORD VERIFICATION")

    if not user:
        print_result("Result", "Cannot verify - user not found", "error")
        return False

    if not user.PASSWORD:
        print_result("Result", "No password hash stored", "error")
        return False

    # Try to verify
    try:
        is_valid = pwd_context.verify(password, user.PASSWORD)
        print_result("Password valid", "YES" if is_valid else "NO", "ok" if is_valid else "error")

        if not is_valid:
            print_result("Hint", "Password hash may be in different format or password is wrong", "warn")
            # Check if it's a bcrypt hash
            if user.PASSWORD.startswith("$2"):
                print_result("Hash format", "Bcrypt (expected)", "ok")
            else:
                print_result("Hash format", f"Unknown - starts with: {user.PASSWORD[:10]}", "warn")

        return is_valid
    except Exception as e:
        print_result("Verification error", str(e), "error")
        return False


def check_database_roles(db, user: SysSecUser):
    """Check roles in sys_sec_user_role table"""
    print_header("3. DATABASE ROLES (sys_sec_user_role)")

    if not user:
        print_result("Result", "Cannot check - user not found", "error")
        return []

    # Query user roles with role names
    user_roles = db.query(SysSecUserRole, SysSecRole).join(
        SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
    ).filter(SysSecUserRole.People == user.oid).all()

    if not user_roles:
        print_result("Database roles", "NONE - User has no roles assigned", "warn")
        return []

    print_result("Number of roles", len(user_roles), "ok")
    print()

    roles = []
    for ur, role in user_roles:
        print(f"    Role: {role.Name}")
        print(f"      - Role OID: {role.Oid}")
        print(f"      - Is Administrative: {role.IsAdministrative}")
        print(f"      - Can Edit Model: {role.CanEditModel}")
        print(f"      - Permission Policy: {role.PermissionPolicy}")
        roles.append(role.Name)

    return roles


def check_casbin_roles(user: SysSecUser):
    """Check roles in Casbin"""
    print_header("4. CASBIN ROLES (casbin_rule table - 'g' policies)")

    if not user:
        print_result("Result", "Cannot check - user not found", "error")
        return []

    user_id_str = str(user.oid)

    try:
        # Initialize Casbin
        CasbinService.initialize()

        # Get roles for user
        roles = CasbinService.get_roles_for_user(user_id_str)

        if not roles:
            print_result("Casbin roles", "NONE - User has no roles in Casbin", "warn")
        else:
            print_result("Number of roles", len(roles), "ok")
            for role in roles:
                print(f"    - {role}")

        return roles
    except Exception as e:
        print_result("Error", str(e), "error")
        return []


def check_casbin_permissions(user: SysSecUser):
    """Check permissions in Casbin"""
    print_header("5. CASBIN PERMISSIONS")

    if not user:
        print_result("Result", "Cannot check - user not found", "error")
        return

    user_id_str = str(user.oid)

    try:
        # Get direct permissions
        direct_perms = CasbinService.get_permissions_for_user(user_id_str)
        print_result("Direct permissions", len(direct_perms))
        for perm in direct_perms[:10]:  # Show first 10
            print(f"    {perm}")
        if len(direct_perms) > 10:
            print(f"    ... and {len(direct_perms) - 10} more")

        # Get implicit permissions (including role-inherited)
        implicit_perms = CasbinService.get_implicit_permissions_for_user(user_id_str)
        print_result("Implicit permissions (incl. role-inherited)", len(implicit_perms))
        for perm in implicit_perms[:10]:  # Show first 10
            print(f"    {perm}")
        if len(implicit_perms) > 10:
            print(f"    ... and {len(implicit_perms) - 10} more")

    except Exception as e:
        print_result("Error", str(e), "error")


def check_all_casbin_policies():
    """Show all Casbin policies for debugging"""
    print_header("6. ALL CASBIN POLICIES (for reference)")

    try:
        # Get all policies
        policies = CasbinService.get_policy()
        print_result("Total permission policies (p)", len(policies))
        for policy in policies[:15]:  # Show first 15
            print(f"    p: {policy}")
        if len(policies) > 15:
            print(f"    ... and {len(policies) - 15} more")

        print()

        # Get all role assignments
        groupings = CasbinService.get_grouping_policy()
        print_result("Total role assignments (g)", len(groupings))
        for g in groupings[:15]:  # Show first 15
            print(f"    g: {g}")
        if len(groupings) > 15:
            print(f"    ... and {len(groupings) - 15} more")

    except Exception as e:
        print_result("Error", str(e), "error")


def test_jwt_token(user: SysSecUser):
    """Test JWT token creation and decoding"""
    print_header("7. JWT TOKEN TEST")

    if not user:
        print_result("Result", "Cannot test - user not found", "error")
        return

    try:
        # Create token
        token_data = {
            "sub": str(user.oid),
            "username": user.USERNAME
        }
        token = create_access_token(token_data)
        print_result("Token created", "YES", "ok")
        print_result("Token preview", token[:50] + "...")

        # Decode token
        payload = decode_token(token)
        print_result("Token decoded", "YES", "ok")
        print_result("Payload sub (user_id)", payload.get("sub"))
        print_result("Payload username", payload.get("username"))
        print_result("Payload exp", datetime.fromtimestamp(payload.get("exp")))

        # Show JWT config
        print()
        print_result("JWT Secret Key (first 20 chars)", SECRET_KEY[:20] + "...")
        print_result("JWT Algorithm", ALGORITHM)

    except Exception as e:
        print_result("Error", str(e), "error")


def test_casbin_enforcement(user: SysSecUser):
    """Test Casbin enforcement for common resources"""
    print_header("8. CASBIN ENFORCEMENT TEST")

    if not user:
        print_result("Result", "Cannot test - user not found", "error")
        return

    user_id_str = str(user.oid)

    # Test common resource/action combinations
    test_cases = [
        ("msession:*", "read"),
        ("msession:*", "write"),
        ("msession:*", "delete"),
        ("image:*", "read"),
        ("image:*", "write"),
        ("*", "*"),
        ("action:export", "execute"),
        ("navigation:/admin", "navigate"),
    ]

    print("  Testing common permission checks:")
    print()

    for resource, action in test_cases:
        try:
            result = CasbinService.enforce(user_id_str, resource, action)
            status = "ok" if result else "warn"
            print(f"    enforce({user_id_str[:8]}..., '{resource}', '{action}') = {result}")
        except Exception as e:
            print(f"    enforce({user_id_str[:8]}..., '{resource}', '{action}') = ERROR: {e}")


def compare_db_vs_casbin_roles(db_roles: list, casbin_roles: list):
    """Compare database roles with Casbin roles"""
    print_header("9. DATABASE vs CASBIN ROLES COMPARISON")

    db_set = set(db_roles)
    casbin_set = set(casbin_roles)

    print_result("Database roles", db_roles if db_roles else "None")
    print_result("Casbin roles", casbin_roles if casbin_roles else "None")

    # Check for mismatches
    in_db_not_casbin = db_set - casbin_set
    in_casbin_not_db = casbin_set - db_set

    if in_db_not_casbin:
        print_result("In DB but NOT in Casbin", list(in_db_not_casbin), "error")
        print_result("Action needed", "Run policy sync script to add missing roles to Casbin", "warn")

    if in_casbin_not_db:
        print_result("In Casbin but NOT in DB", list(in_casbin_not_db), "warn")

    if not in_db_not_casbin and not in_casbin_not_db:
        if db_roles:
            print_result("Roles match", "YES - DB and Casbin roles are in sync", "ok")
        else:
            print_result("Status", "No roles in either DB or Casbin", "warn")


def main():
    if len(sys.argv) < 3:
        print("Usage: python test_user_auth_debug.py <username> <password>")
        print("Example: python test_user_auth_debug.py super mypassword")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    print("\n" + "#" * 60)
    print(f"# USER AUTHENTICATION DEBUG REPORT")
    print(f"# Username: {username}")
    print(f"# Time: {datetime.now()}")
    print("#" * 60)

    # Create database session
    db = create_db_session()

    try:
        # Run all checks
        user = check_user_in_database(db, username)
        password_valid = check_password(user, password)
        db_roles = check_database_roles(db, user)
        casbin_roles = check_casbin_roles(user)
        check_casbin_permissions(user)
        check_all_casbin_policies()
        test_jwt_token(user)
        test_casbin_enforcement(user)
        compare_db_vs_casbin_roles(db_roles, casbin_roles)

        # Summary
        print_header("SUMMARY")

        issues = []
        if not user:
            issues.append("User not found in database")
        elif not user.ACTIVE:
            issues.append("User is inactive")
        elif user.GCRecord is not None:
            issues.append("User is soft-deleted")

        if not password_valid:
            issues.append("Password verification failed")

        if not db_roles:
            issues.append("No roles assigned in database")

        if not casbin_roles:
            issues.append("No roles in Casbin (policy not synced?)")

        if db_roles and casbin_roles and set(db_roles) != set(casbin_roles):
            issues.append("Database and Casbin roles are out of sync")

        if issues:
            print("  ISSUES FOUND:")
            for issue in issues:
                print(f"    [X] {issue}")
            print()
            print("  POSSIBLE SOLUTIONS:")
            if "User not found" in str(issues):
                print("    - Check username spelling")
                print("    - Create user via /api/security/setup endpoint")
            if "Password verification failed" in str(issues):
                print("    - Reset password via admin endpoint")
                print("    - Check if password was hashed correctly")
            if "No roles" in str(issues) or "sync" in str(issues):
                print("    - Run: python scripts/sync_policies_to_casbin.py")
                print("    - Or call: POST /api/security/roles/sync")
        else:
            print("  [OK] No issues found - user should be able to authenticate")

    finally:
        db.close()


if __name__ == "__main__":
    main()
