"""
Basic tests for Casbin authorization service

Run with: pytest tests/test_casbin_basic.py -v
"""
import pytest
from services.casbin_service import CasbinService


@pytest.fixture(scope="module", autouse=True)
def setup_casbin():
    """Initialize Casbin enforcer before tests"""
    CasbinService.initialize()
    # Clear any existing test data
    CasbinService.clear_policy()
    yield
    # Cleanup after tests
    CasbinService.clear_policy()


def test_casbin_initialization():
    """Test that Casbin initializes correctly"""
    enforcer = CasbinService.get_enforcer()
    assert enforcer is not None
    assert enforcer.get_model() is not None


def test_role_assignment():
    """Test adding and checking roles"""
    user_id = "test-user-123"
    role_name = "TestRole"

    # Add role
    result = CasbinService.add_role_for_user(user_id, role_name)
    assert result is True

    # Check role exists
    has_role = CasbinService.has_role_for_user(user_id, role_name)
    assert has_role is True

    # Get roles list
    roles = CasbinService.get_roles_for_user(user_id)
    assert role_name in roles

    # Get users for role
    users = CasbinService.get_users_for_role(role_name)
    assert user_id in users

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)


def test_direct_user_permission():
    """Test adding direct permission to user (not via role)"""
    user_id = "test-user-456"
    resource = "test-resource:123"
    action = "read"

    # Add permission
    CasbinService.add_permission_for_user(user_id, resource, action, "allow")

    # Check permission is granted
    has_permission = CasbinService.enforce(user_id, resource, action)
    assert has_permission is True

    # Check denied permission
    has_write = CasbinService.enforce(user_id, resource, "write")
    assert has_write is False

    # Cleanup
    CasbinService.delete_permission_for_user(user_id, resource, action)


def test_role_based_permission():
    """Test permissions inherited through roles"""
    user_id = "test-user-789"
    role_name = "TestEditor"
    resource = "document:123"
    action = "edit"

    # Add role to user
    CasbinService.add_role_for_user(user_id, role_name)

    # Add permission to role
    CasbinService.add_permission_for_role(role_name, resource, action, "allow")

    # User should have permission via role
    has_permission = CasbinService.enforce(user_id, resource, action)
    assert has_permission is True

    # User should NOT have other permissions
    has_delete = CasbinService.enforce(user_id, resource, "delete")
    assert has_delete is False

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)
    CasbinService.delete_permission_for_role(role_name, resource, action)


def test_wildcard_resource_permissions():
    """Test wildcard resource matching (e.g., msession:*)"""
    user_id = "test-user-wildcard"
    role_name = "SessionViewer"

    # Add role to user
    CasbinService.add_role_for_user(user_id, role_name)

    # Add wildcard permission to role
    CasbinService.add_permission_for_role(role_name, "msession:*", "read", "allow")

    # User should be able to read ANY msession
    assert CasbinService.enforce(user_id, "msession:123", "read") is True
    assert CasbinService.enforce(user_id, "msession:456", "read") is True
    assert CasbinService.enforce(user_id, "msession:abc-def", "read") is True

    # But not write
    assert CasbinService.enforce(user_id, "msession:123", "write") is False

    # And not other resources
    assert CasbinService.enforce(user_id, "project:123", "read") is False

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)
    CasbinService.delete_permission_for_role(role_name, "msession:*", "read")


def test_wildcard_action_permissions():
    """Test wildcard action matching (action = *)"""
    user_id = "test-user-wildcard-action"
    role_name = "SuperUser"
    resource = "admin:panel"

    # Add role
    CasbinService.add_role_for_user(user_id, role_name)

    # Add permission with wildcard action
    CasbinService.add_permission_for_role(role_name, resource, "*", "allow")

    # User should be able to perform ANY action
    assert CasbinService.enforce(user_id, resource, "read") is True
    assert CasbinService.enforce(user_id, resource, "write") is True
    assert CasbinService.enforce(user_id, resource, "delete") is True
    assert CasbinService.enforce(user_id, resource, "execute") is True

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)
    CasbinService.delete_permission_for_role(role_name, resource, "*")


def test_administrator_bypass():
    """Test that Administrator role has access to everything"""
    user_id = "test-admin-user"
    role_name = "Administrator"

    # Add admin role to user
    CasbinService.add_role_for_user(user_id, role_name)

    # Even without explicit permissions, admin should have access to everything
    # (based on matcher in casbin_model.conf)
    assert CasbinService.enforce(user_id, "any-resource:123", "read") is True
    assert CasbinService.enforce(user_id, "any-resource:456", "write") is True
    assert CasbinService.enforce(user_id, "msession:999", "delete") is True

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)


def test_deny_overrides_allow():
    """Test that deny policy overrides allow policy"""
    user_id = "test-deny-user"
    role_allow = "AllowRole"
    role_deny = "DenyRole"
    resource = "sensitive:data"

    # User has two roles
    CasbinService.add_role_for_user(user_id, role_allow)
    CasbinService.add_role_for_user(user_id, role_deny)

    # One role allows, one denies
    CasbinService.add_permission_for_role(role_allow, resource, "read", "allow")
    CasbinService.add_permission_for_role(role_deny, resource, "read", "deny")

    # Deny should win (based on policy effect in model.conf)
    has_permission = CasbinService.enforce(user_id, resource, "read")
    assert has_permission is False

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_allow)
    CasbinService.delete_role_for_user(user_id, role_deny)
    CasbinService.delete_permission_for_role(role_allow, resource, "read", "allow")
    CasbinService.delete_permission_for_role(role_deny, resource, "read", "deny")


def test_batch_enforce():
    """Test batch permission checking"""
    user_id = "test-batch-user"
    role_name = "BatchTester"

    # Setup
    CasbinService.add_role_for_user(user_id, role_name)
    CasbinService.add_permission_for_role(role_name, "resource:1", "read", "allow")
    CasbinService.add_permission_for_role(role_name, "resource:2", "read", "allow")

    # Batch check
    requests = [
        (user_id, "resource:1", "read"),  # Should be True
        (user_id, "resource:2", "read"),  # Should be True
        (user_id, "resource:3", "read"),  # Should be False
        (user_id, "resource:1", "write"), # Should be False
    ]

    results = CasbinService.batch_enforce(requests)

    assert results == [True, True, False, False]

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)
    CasbinService.delete_permission_for_role(role_name, "resource:1", "read")
    CasbinService.delete_permission_for_role(role_name, "resource:2", "read")


def test_get_permissions_for_user():
    """Test retrieving all permissions for a user"""
    user_id = "test-perms-user"
    role_name = "TestRole"

    # Setup
    CasbinService.add_role_for_user(user_id, role_name)
    CasbinService.add_permission_for_role(role_name, "res:1", "read", "allow")
    CasbinService.add_permission_for_role(role_name, "res:2", "write", "allow")

    # Get implicit permissions (includes role-inherited)
    perms = CasbinService.get_implicit_permissions_for_user(user_id)

    # Should have 2 permissions
    assert len(perms) >= 2

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)
    CasbinService.delete_permission_for_role(role_name, "res:1", "read")
    CasbinService.delete_permission_for_role(role_name, "res:2", "write")


def test_multiple_roles():
    """Test user with multiple roles"""
    user_id = "test-multi-role-user"
    role1 = "Viewer"
    role2 = "Editor"

    # Assign multiple roles
    CasbinService.add_role_for_user(user_id, role1)
    CasbinService.add_role_for_user(user_id, role2)

    # Add different permissions to each role
    CasbinService.add_permission_for_role(role1, "doc:123", "read", "allow")
    CasbinService.add_permission_for_role(role2, "doc:123", "write", "allow")

    # User should have both permissions
    assert CasbinService.enforce(user_id, "doc:123", "read") is True
    assert CasbinService.enforce(user_id, "doc:123", "write") is True

    # Get all roles
    roles = CasbinService.get_roles_for_user(user_id)
    assert len(roles) == 2
    assert role1 in roles
    assert role2 in roles

    # Cleanup
    CasbinService.delete_roles_for_user(user_id)
    CasbinService.delete_permission_for_role(role1, "doc:123", "read")
    CasbinService.delete_permission_for_role(role2, "doc:123", "write")


def test_policy_persistence():
    """Test that policies are saved to database"""
    user_id = "test-persist-user"
    role_name = "PersistRole"

    # Add policy
    CasbinService.add_role_for_user(user_id, role_name)
    CasbinService.add_permission_for_role(role_name, "persist:res", "read", "allow")

    # Check it exists
    assert CasbinService.has_role_for_user(user_id, role_name) is True

    # Reload policies from database
    CasbinService.reload_policy()

    # Should still exist after reload
    assert CasbinService.has_role_for_user(user_id, role_name) is True
    assert CasbinService.enforce(user_id, "persist:res", "read") is True

    # Cleanup
    CasbinService.delete_role_for_user(user_id, role_name)
    CasbinService.delete_permission_for_role(role_name, "persist:res", "read")
