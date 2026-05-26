from __future__ import annotations

import pytest

from services.casbin_service import CasbinService


class FakeEnforcer:
    def __init__(self):
        self.policies: list[list[str]] = []
        self.grouping: list[list[str]] = []
        self.enforce_calls = 0

    def get_policy(self):
        return [list(policy) for policy in self.policies]

    def get_grouping_policy(self):
        return [list(grouping) for grouping in self.grouping]

    def enforce(self, *args):
        self.enforce_calls += 1
        raise AssertionError("CasbinService should use its authorization index")

    def add_role_for_user(self, user_id, role_name):
        entry = [user_id, role_name]
        if entry in self.grouping:
            return False
        self.grouping.append(entry)
        return True

    def delete_role_for_user(self, user_id, role_name):
        entry = [user_id, role_name]
        if entry not in self.grouping:
            return False
        self.grouping.remove(entry)
        return True

    def delete_roles_for_user(self, user_id):
        before = len(self.grouping)
        self.grouping = [entry for entry in self.grouping if entry[0] != user_id]
        return len(self.grouping) != before

    def add_policy(self, subject, resource, action, effect):
        entry = [subject, resource, action, effect]
        if entry in self.policies:
            return False
        self.policies.append(entry)
        return True

    def remove_policy(self, subject, resource, action, effect):
        entry = [subject, resource, action, effect]
        if entry not in self.policies:
            return False
        self.policies.remove(entry)
        return True

    def remove_filtered_policy(self, field_index, *field_values):
        before = len(self.policies)
        filtered = []
        for policy in self.policies:
            fields = policy[field_index:field_index + len(field_values)]
            if tuple(fields) == tuple(field_values):
                continue
            filtered.append(policy)
        self.policies = filtered
        return len(self.policies) != before


@pytest.fixture
def fake_enforcer(monkeypatch):
    fake = FakeEnforcer()
    monkeypatch.setattr(CasbinService, "_enforcer", fake)
    CasbinService._invalidate_authorization_cache()
    yield fake
    CasbinService._invalidate_authorization_cache()


def test_enforce_uses_index_for_role_permissions(fake_enforcer):
    fake_enforcer.grouping.append(["user-1", "Researcher"])
    fake_enforcer.policies.append(["Researcher", "msession:1", "read", "allow"])

    assert CasbinService.enforce("user-1", "msession:1", "read") is True
    assert fake_enforcer.enforce_calls == 0


def test_index_matches_deny_override_and_wildcard_resources(fake_enforcer):
    fake_enforcer.grouping.append(["user-1", "Researcher"])
    fake_enforcer.policies.extend([
        ["Researcher", "msession:*", "read", "allow"],
        ["user-1", "msession:blocked", "read", "deny"],
    ])

    assert CasbinService.enforce("user-1", "msession:allowed", "read") is True
    assert CasbinService.enforce("user-1", "msession:blocked", "read") is False


def test_index_cache_invalidates_after_policy_mutation(fake_enforcer):
    CasbinService.add_role_for_user("user-1", "Researcher")

    assert CasbinService.enforce("user-1", "msession:1", "read") is False

    CasbinService.add_permission_for_role("Researcher", "msession:1", "read", "allow")
    assert CasbinService.enforce("user-1", "msession:1", "read") is True

    CasbinService.add_permission_for_role("Researcher", "msession:1", "read", "deny")
    assert CasbinService.enforce("user-1", "msession:1", "read") is False


def test_index_expands_transitive_role_assignments(fake_enforcer):
    CasbinService.add_role_for_user("user-1", "Researcher")
    CasbinService.add_role_for_user("Researcher", "Administrator")
    CasbinService.add_permission_for_role("Administrator", "*", "*", "allow")

    assert CasbinService.enforce("user-1", "any:resource", "delete") is True
