"""
Comprehensive Test Suite for Row-Level Security

Tests the complete flow:
1. Criteria parsing
2. Casbin sync
3. Permission enforcement
4. Session access management

Run with: pytest tests/test_row_level_security.py -v
"""
import pytest
from uuid import uuid4, UUID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from services.security.criteria_parser_service import (
    CriteriaParserService,
    CasbinResourceBuilder
)
from services.casbin_service import CasbinService
from services.casbin_policy_sync_service import CasbinPolicySyncService


# ==================== CRITERIA PARSER TESTS ====================

class TestCriteriaParser:
    """Test criteria parsing functionality"""

    def test_parse_simple_equality(self):
        """Test parsing simple equality: [session_id] = 'uuid'"""
        session_id = str(uuid4())
        criteria = f"[session_id] = '{session_id}'"

        resources = CriteriaParserService.parse_criteria(criteria, "Image")

        assert len(resources) == 1
        assert resources[0] == f"image:{session_id}"

    def test_parse_in_clause(self):
        """Test parsing IN clause: [session_id] IN ('uuid1', 'uuid2')"""
        session_id1 = str(uuid4())
        session_id2 = str(uuid4())
        criteria = f"[session_id] IN ('{session_id1}', '{session_id2}')"

        resources = CriteriaParserService.parse_criteria(criteria, "Image")

        assert len(resources) == 2
        assert f"image:{session_id1}" in resources
        assert f"image:{session_id2}" in resources

    def test_parse_msession_type(self):
        """Test parsing with Msession target type"""
        session_id = str(uuid4())
        criteria = f"[oid] = '{session_id}'"

        resources = CriteriaParserService.parse_criteria(criteria, "Msession")

        assert len(resources) == 1
        assert resources[0] == f"msession:{session_id}"

    def test_can_sync_to_casbin_simple(self):
        """Test can_sync_to_casbin with simple criteria"""
        session_id = str(uuid4())
        criteria = f"[session_id] = '{session_id}'"

        assert CriteriaParserService.can_sync_to_casbin(criteria) == True

    def test_can_sync_to_casbin_dynamic(self):
        """Test can_sync_to_casbin with dynamic criteria"""
        criteria = "[user_id] = CurrentUserId()"

        assert CriteriaParserService.can_sync_to_casbin(criteria) == False

    def test_parse_and_categorize_simple(self):
        """Test parse_and_categorize with simple criteria"""
        session_id = str(uuid4())
        criteria = f"[session_id] = '{session_id}'"

        result = CriteriaParserService.parse_and_categorize(criteria, "Image")

        assert result["can_sync_to_casbin"] == True
        assert result["handling"] == "casbin"
        assert result["complexity"] == "simple"
        assert len(result["resources"]) == 1

    def test_parse_and_categorize_dynamic(self):
        """Test parse_and_categorize with dynamic criteria"""
        criteria = "[user_id] = CurrentUserId()"

        result = CriteriaParserService.parse_and_categorize(criteria, "Image")

        assert result["can_sync_to_casbin"] == False
        assert result["handling"] == "hybrid"
        assert result["complexity"] == "dynamic"

    def test_parse_empty_criteria(self):
        """Test parsing empty criteria"""
        resources = CriteriaParserService.parse_criteria("", "Image")

        assert len(resources) == 0

    def test_parse_complex_criteria(self):
        """Test parsing complex criteria that can't be synced"""
        criteria = "[status] = 'active' AND [user_id] = 'abc'"

        result = CriteriaParserService.parse_and_categorize(criteria, "Image")

        assert result["can_sync_to_casbin"] == False


# ==================== CASBIN RESOURCE BUILDER TESTS ====================

class TestCasbinResourceBuilder:
    """Test Casbin resource identifier building"""

    def test_build_session_resource(self):
        """Test building session resource identifier"""
        session_id = uuid4()
        resource = CasbinResourceBuilder.build_session_resource(session_id)

        assert resource == f"msession:{session_id}"

    def test_build_image_resource(self):
        """Test building image resource identifier"""
        image_id = uuid4()
        resource = CasbinResourceBuilder.build_image_resource(image_id)

        assert resource == f"image:{image_id}"

    def test_build_wildcard_resource(self):
        """Test building wildcard resource"""
        resource = CasbinResourceBuilder.build_wildcard_resource("msession")

        assert resource == "msession:*"

    def test_parse_resource(self):
        """Test parsing resource identifier"""
        session_id = uuid4()
        resource = f"msession:{session_id}"

        resource_type, resource_id = CasbinResourceBuilder.parse_resource(resource)

        assert resource_type == "msession"
        assert resource_id == str(session_id)

    def test_is_wildcard(self):
        """Test wildcard detection"""
        assert CasbinResourceBuilder.is_wildcard("msession:*") == True
        assert CasbinResourceBuilder.is_wildcard(f"msession:{uuid4()}") == False

    def test_is_instance_resource(self):
        """Test instance resource detection"""
        assert CasbinResourceBuilder.is_instance_resource("msession:*") == False
        assert CasbinResourceBuilder.is_instance_resource(f"msession:{uuid4()}") == True


# ==================== CASBIN INTEGRATION TESTS ====================

class TestCasbinIntegration:
    """Test Casbin service integration"""

    def setup_method(self):
        """Initialize Casbin enforcer before each test"""
        CasbinService.initialize()
        CasbinService.clear_policy()

    def test_type_level_permission(self):
        """Test type-level wildcard permission"""
        user_id = str(uuid4())
        role_name = "Researcher"

        # Add role to user
        CasbinService.add_role_for_user(user_id, role_name)

        # Add type-level permission
        CasbinService.add_permission_for_role(role_name, "msession:*", "read", "allow")

        # User should be able to read any session
        session_id = str(uuid4())
        resource = f"msession:{session_id}"

        assert CasbinService.enforce(user_id, resource, "read") == True
        assert CasbinService.enforce(user_id, resource, "write") == False

    def test_instance_level_permission(self):
        """Test instance-level specific permission"""
        user_id = str(uuid4())
        role_name = "Researcher"
        session_id_allowed = str(uuid4())
        session_id_denied = str(uuid4())

        # Add role to user
        CasbinService.add_role_for_user(user_id, role_name)

        # Add permission for specific session only
        resource_allowed = f"msession:{session_id_allowed}"
        CasbinService.add_permission_for_role(role_name, resource_allowed, "read", "allow")

        # User can read allowed session
        assert CasbinService.enforce(user_id, resource_allowed, "read") == True

        # User cannot read other session
        resource_denied = f"msession:{session_id_denied}"
        assert CasbinService.enforce(user_id, resource_denied, "read") == False

    def test_multiple_session_permissions(self):
        """Test user with access to multiple specific sessions"""
        user_id = str(uuid4())
        role_name = "Researcher"
        session_id1 = str(uuid4())
        session_id2 = str(uuid4())
        session_id3 = str(uuid4())

        # Add role to user
        CasbinService.add_role_for_user(user_id, role_name)

        # Grant access to session 1 and 2 only
        CasbinService.add_permission_for_role(role_name, f"msession:{session_id1}", "read", "allow")
        CasbinService.add_permission_for_role(role_name, f"msession:{session_id2}", "read", "allow")

        # Can access sessions 1 and 2
        assert CasbinService.enforce(user_id, f"msession:{session_id1}", "read") == True
        assert CasbinService.enforce(user_id, f"msession:{session_id2}", "read") == True

        # Cannot access session 3
        assert CasbinService.enforce(user_id, f"msession:{session_id3}", "read") == False

    def test_admin_role_has_all_access(self):
        """Test administrator role has wildcard access"""
        user_id = str(uuid4())

        # Add Administrator role
        CasbinService.add_role_for_user(user_id, "Administrator")

        # Administrator should NOT automatically have access
        # (unless explicitly granted via policy)
        session_id = str(uuid4())
        resource = f"msession:{session_id}"

        # Need to add wildcard permission for admin
        CasbinService.add_permission_for_role("Administrator", "msession:*", "*", "allow")

        assert CasbinService.enforce(user_id, resource, "read") == True
        assert CasbinService.enforce(user_id, resource, "write") == True
        assert CasbinService.enforce(user_id, resource, "delete") == True

    def test_deny_overrides_allow(self):
        """Test that deny policies override allow policies"""
        user_id = str(uuid4())
        role_name = "Researcher"
        session_id = str(uuid4())
        resource = f"msession:{session_id}"

        # Add role to user
        CasbinService.add_role_for_user(user_id, role_name)

        # Add allow policy
        CasbinService.add_permission_for_role(role_name, resource, "read", "allow")

        # Verify allow works
        assert CasbinService.enforce(user_id, resource, "read") == True

        # Add deny policy (explicit deny)
        CasbinService.add_permission_for_role(role_name, resource, "read", "deny")

        # Deny should override allow
        assert CasbinService.enforce(user_id, resource, "read") == False


# ==================== END-TO-END SCENARIO TESTS ====================

class TestEndToEndScenarios:
    """Test complete end-to-end scenarios"""

    def setup_method(self):
        """Setup test environment"""
        CasbinService.initialize()
        CasbinService.clear_policy()

    def test_scenario_jack_has_access_to_session_a_and_b(self):
        """
        Scenario: Admin grants Jack access to Session A and B only

        Expected: Jack can read A and B, but not C
        """
        # Setup
        jack_id = str(uuid4())
        researcher_role = "Researcher"
        session_a = str(uuid4())
        session_b = str(uuid4())
        session_c = str(uuid4())

        # Step 1: Assign Jack to Researcher role
        CasbinService.add_role_for_user(jack_id, researcher_role)

        # Step 2: Grant Researcher access to Session A and B
        CasbinService.add_permission_for_role(
            researcher_role, f"msession:{session_a}", "read", "allow"
        )
        CasbinService.add_permission_for_role(
            researcher_role, f"msession:{session_b}", "read", "allow"
        )

        # Step 3: Test enforcement
        # Jack can access Session A
        assert CasbinService.enforce(jack_id, f"msession:{session_a}", "read") == True

        # Jack can access Session B
        assert CasbinService.enforce(jack_id, f"msession:{session_b}", "read") == True

        # Jack CANNOT access Session C
        assert CasbinService.enforce(jack_id, f"msession:{session_c}", "read") == False

    def test_scenario_admin_revokes_access(self):
        """
        Scenario: Admin grants then revokes Jack's access to Session A

        Expected: Jack initially has access, then loses it after revoke
        """
        # Setup
        jack_id = str(uuid4())
        researcher_role = "Researcher"
        session_a = str(uuid4())

        # Step 1: Grant access
        CasbinService.add_role_for_user(jack_id, researcher_role)
        CasbinService.add_permission_for_role(
            researcher_role, f"msession:{session_a}", "read", "allow"
        )

        # Jack has access
        assert CasbinService.enforce(jack_id, f"msession:{session_a}", "read") == True

        # Step 2: Revoke access (remove policy)
        CasbinService.delete_permission_for_role(
            researcher_role, f"msession:{session_a}", "read", "allow"
        )

        # Jack no longer has access
        assert CasbinService.enforce(jack_id, f"msession:{session_a}", "read") == False

    def test_scenario_multiple_users_same_session(self):
        """
        Scenario: Multiple users (Jack, Sarah) have access to Session A

        Expected: Both can access Session A
        """
        # Setup
        jack_id = str(uuid4())
        sarah_id = str(uuid4())
        researcher_role = "Researcher"
        session_a = str(uuid4())

        # Assign both to Researcher role
        CasbinService.add_role_for_user(jack_id, researcher_role)
        CasbinService.add_role_for_user(sarah_id, researcher_role)

        # Grant Researcher access to Session A
        CasbinService.add_permission_for_role(
            researcher_role, f"msession:{session_a}", "read", "allow"
        )

        # Both can access
        assert CasbinService.enforce(jack_id, f"msession:{session_a}", "read") == True
        assert CasbinService.enforce(sarah_id, f"msession:{session_a}", "read") == True

    def test_scenario_read_only_vs_read_write(self):
        """
        Scenario: Jack has read-only, Sarah has read-write on Session A

        Expected: Jack can read but not write, Sarah can do both
        """
        # Setup
        jack_id = str(uuid4())
        sarah_id = str(uuid4())
        read_only_role = "ReadOnly"
        read_write_role = "ReadWrite"
        session_a = str(uuid4())

        # Assign roles
        CasbinService.add_role_for_user(jack_id, read_only_role)
        CasbinService.add_role_for_user(sarah_id, read_write_role)

        # Grant permissions
        CasbinService.add_permission_for_role(
            read_only_role, f"msession:{session_a}", "read", "allow"
        )
        CasbinService.add_permission_for_role(
            read_write_role, f"msession:{session_a}", "read", "allow"
        )
        CasbinService.add_permission_for_role(
            read_write_role, f"msession:{session_a}", "write", "allow"
        )

        # Jack can read but not write
        assert CasbinService.enforce(jack_id, f"msession:{session_a}", "read") == True
        assert CasbinService.enforce(jack_id, f"msession:{session_a}", "write") == False

        # Sarah can read and write
        assert CasbinService.enforce(sarah_id, f"msession:{session_a}", "read") == True
        assert CasbinService.enforce(sarah_id, f"msession:{session_a}", "write") == True


# ==================== PERFORMANCE TESTS ====================

class TestPerformance:
    """Test performance of permission checks"""

    def setup_method(self):
        """Setup large dataset"""
        CasbinService.initialize()
        CasbinService.clear_policy()

    def test_performance_100_sessions(self):
        """Test performance with 100 sessions"""
        import time

        user_id = str(uuid4())
        role_name = "Researcher"

        CasbinService.add_role_for_user(user_id, role_name)

        # Grant access to 100 sessions
        session_ids = [str(uuid4()) for _ in range(100)]
        for session_id in session_ids:
            CasbinService.add_permission_for_role(
                role_name, f"msession:{session_id}", "read", "allow"
            )

        # Test enforcement speed
        start_time = time.time()
        for session_id in session_ids:
            CasbinService.enforce(user_id, f"msession:{session_id}", "read")
        end_time = time.time()

        elapsed = end_time - start_time
        avg_time = elapsed / 100

        # Should be very fast (< 1ms per check)
        assert avg_time < 0.001  # Less than 1 millisecond per check
        print(f"\\nAverage enforcement time: {avg_time*1000:.2f}ms")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
