"""
Casbin Authorization Service

This service wraps Casbin enforcer and provides authorization checking.
Integrates with existing sys_sec_* security tables.
"""
import casbin
from casbin_sqlalchemy_adapter import Adapter
from typing import Optional, List
import logging

from database import engine

logger = logging.getLogger(__name__)


class CasbinService:
    """Singleton service for Casbin enforcer"""

    _enforcer: Optional[casbin.Enforcer] = None
    _adapter: Optional[Adapter] = None

    @classmethod
    def initialize(cls):
        """Initialize Casbin enforcer with SQLAlchemy adapter"""
        if cls._enforcer is None:
            try:
                logger.info("Initializing Casbin enforcer...")

                # Create adapter (creates casbin_rule table automatically)
                cls._adapter = Adapter(engine, db_class=None)
                logger.info("[OK] Casbin SQLAlchemy adapter created")

                # Load model and create enforcer
                model_path = "configs/casbin_model.conf"
                cls._enforcer = casbin.Enforcer(model_path, cls._adapter)
                logger.info(f"[OK] Casbin model loaded from {model_path}")

                # Enable auto-save (policies saved to DB immediately)
                cls._enforcer.enable_auto_save(True)

                # Load all policies from database
                cls._enforcer.load_policy()
                logger.info("[OK] Casbin policies loaded from database")

                # Log policy counts
                policy_count = len(cls._enforcer.get_policy())
                grouping_count = len(cls._enforcer.get_grouping_policy())
                logger.info(f"[OK] Loaded {policy_count} policies and {grouping_count} role assignments")

                logger.info("[OK] Casbin enforcer initialized successfully")

            except Exception as e:
                logger.error(f"[ERROR] Failed to initialize Casbin enforcer: {e}")
                raise

        return cls._enforcer

    @classmethod
    def get_enforcer(cls) -> casbin.Enforcer:
        """Get or create Casbin enforcer instance"""
        if cls._enforcer is None:
            cls.initialize()
        return cls._enforcer

    @classmethod
    def enforce(cls, user_id: str, resource: str, action: str) -> bool:
        """
        Check if user has permission to perform action on resource

        Args:
            user_id: User UUID as string
            resource: Resource identifier (e.g., "msession:abc-123" or "msession:*")
            action: Action to perform (e.g., "read", "write", "delete", "create")

        Returns:
            bool: True if allowed, False otherwise

        Examples:
            >>> CasbinService.enforce("user-123", "msession:abc-456", "read")
            True
            >>> CasbinService.enforce("user-123", "msession:*", "write")
            False
        """
        enforcer = cls.get_enforcer()
        result = enforcer.enforce(user_id, resource, action)
        logger.debug(f"Enforce: user={user_id}, resource={resource}, action={action}, result={result}")
        return result

    @classmethod
    def batch_enforce(cls, requests: List[tuple]) -> List[bool]:
        """
        Batch enforce multiple requests at once (more efficient)

        Args:
            requests: List of (user_id, resource, action) tuples

        Returns:
            List of boolean results

        Example:
            >>> requests = [
            ...     ("user-1", "msession:123", "read"),
            ...     ("user-1", "msession:456", "write"),
            ... ]
            >>> results = CasbinService.batch_enforce(requests)
            >>> # results = [True, False]
        """
        enforcer = cls.get_enforcer()
        return [enforcer.enforce(*req) for req in requests]

    # ==================== Role Management ====================

    @classmethod
    def add_role_for_user(cls, user_id: str, role_name: str) -> bool:
        """
        Assign role to user

        Args:
            user_id: User UUID as string
            role_name: Role name (e.g., "Administrator", "Researcher")

        Returns:
            bool: True if added, False if already exists
        """
        enforcer = cls.get_enforcer()
        result = enforcer.add_role_for_user(user_id, role_name)
        logger.debug(f"Add role: user={user_id}, role={role_name}, result={result}")
        return result

    @classmethod
    def delete_role_for_user(cls, user_id: str, role_name: str) -> bool:
        """Remove role from user"""
        enforcer = cls.get_enforcer()
        result = enforcer.delete_role_for_user(user_id, role_name)
        logger.debug(f"Delete role: user={user_id}, role={role_name}, result={result}")
        return result

    @classmethod
    def delete_roles_for_user(cls, user_id: str) -> bool:
        """Remove all roles from user"""
        enforcer = cls.get_enforcer()
        result = enforcer.delete_roles_for_user(user_id)
        logger.debug(f"Delete all roles for user={user_id}, result={result}")
        return result

    @classmethod
    def get_roles_for_user(cls, user_id: str) -> List[str]:
        """Get all roles for a user"""
        enforcer = cls.get_enforcer()
        return enforcer.get_roles_for_user(user_id)

    @classmethod
    def get_users_for_role(cls, role_name: str) -> List[str]:
        """Get all users with a specific role"""
        enforcer = cls.get_enforcer()
        return enforcer.get_users_for_role(role_name)

    @classmethod
    def has_role_for_user(cls, user_id: str, role_name: str) -> bool:
        """Check if user has a specific role"""
        enforcer = cls.get_enforcer()
        return enforcer.has_role_for_user(user_id, role_name)

    # ==================== Permission Management ====================

    @classmethod
    def add_permission_for_user(cls, user_id: str, resource: str, action: str, effect: str = "allow") -> bool:
        """
        Add direct permission for user (not via role)

        Args:
            user_id: User UUID as string
            resource: Resource identifier
            action: Action to permit
            effect: "allow" or "deny"
        """
        enforcer = cls.get_enforcer()
        result = enforcer.add_policy(user_id, resource, action, effect)
        logger.debug(f"Add user permission: user={user_id}, resource={resource}, action={action}, effect={effect}")
        return result

    @classmethod
    def add_permission_for_role(cls, role_name: str, resource: str, action: str, effect: str = "allow") -> bool:
        """
        Add permission for role

        Args:
            role_name: Role name
            resource: Resource identifier (e.g., "msession:*" for all sessions)
            action: Action to permit (e.g., "read", "write", "*" for all)
            effect: "allow" or "deny"

        Examples:
            >>> CasbinService.add_permission_for_role("Researcher", "msession:*", "read", "allow")
            >>> CasbinService.add_permission_for_role("Admin", "*", "*", "allow")
        """
        enforcer = cls.get_enforcer()
        result = enforcer.add_policy(role_name, resource, action, effect)
        logger.debug(f"Add role permission: role={role_name}, resource={resource}, action={action}, effect={effect}")
        return result

    @classmethod
    def delete_permission_for_user(cls, user_id: str, resource: str, action: str, effect: str = "allow") -> bool:
        """Remove permission from user"""
        enforcer = cls.get_enforcer()
        return enforcer.remove_policy(user_id, resource, action, effect)

    @classmethod
    def delete_permission_for_role(cls, role_name: str, resource: str, action: str, effect: str = "allow") -> bool:
        """Remove permission from role"""
        enforcer = cls.get_enforcer()
        return enforcer.remove_policy(role_name, resource, action, effect)

    @classmethod
    def delete_role(cls, role_name: str) -> bool:
        """
        Delete all policies associated with a role

        This removes all permission policies where the role is the subject,
        but does NOT remove user-role assignments. Use delete_role_for_user
        to remove role assignments from users.

        Args:
            role_name: The role name to delete

        Returns:
            True if any policies were deleted
        """
        enforcer = cls.get_enforcer()
        result = enforcer.remove_filtered_policy(0, role_name)
        logger.debug(f"Delete role policies: role={role_name}, removed={result}")
        return result

    @classmethod
    def get_permissions_for_user(cls, user_id: str) -> List[List[str]]:
        """
        Get all permissions for user (direct and inherited from roles)

        Returns:
            List of [subject, object, action, effect] lists
        """
        enforcer = cls.get_enforcer()
        return enforcer.get_permissions_for_user(user_id)

    @classmethod
    def get_implicit_permissions_for_user(cls, user_id: str) -> List[List[str]]:
        """
        Get all implicit permissions (including role-inherited permissions)

        Returns:
            List of [subject, object, action, effect] lists
        """
        enforcer = cls.get_enforcer()
        return enforcer.get_implicit_permissions_for_user(user_id)

    @classmethod
    def has_permission_for_user(cls, user_id: str, resource: str, action: str) -> bool:
        """Check if user has specific permission"""
        return cls.enforce(user_id, resource, action)

    # ==================== Policy Management ====================

    @classmethod
    def get_policy(cls) -> List[List[str]]:
        """Get all policies"""
        enforcer = cls.get_enforcer()
        return enforcer.get_policy()

    @classmethod
    def get_grouping_policy(cls) -> List[List[str]]:
        """Get all role assignments (user-role mappings)"""
        enforcer = cls.get_enforcer()
        return enforcer.get_grouping_policy()

    @classmethod
    def clear_policy(cls):
        """
        Clear all policies (dangerous!)

        Use this before re-syncing from sys_sec_* tables
        """
        enforcer = cls.get_enforcer()
        enforcer.clear_policy()
        logger.warning("[WARNING] All Casbin policies cleared")

    @classmethod
    def reload_policy(cls):
        """Reload policies from database"""
        enforcer = cls.get_enforcer()
        enforcer.load_policy()
        logger.info("Policies reloaded from database")

    @classmethod
    def save_policy(cls):
        """
        Save policies to database

        Note: Auto-save is enabled by default, so this is usually not needed
        """
        enforcer = cls.get_enforcer()
        enforcer.save_policy()
        logger.info("Policies saved to database")

    # ==================== Utility Methods ====================

    @classmethod
    def get_all_subjects(cls) -> List[str]:
        """Get all subjects (users and roles) in policies"""
        enforcer = cls.get_enforcer()
        return enforcer.get_all_subjects()

    @classmethod
    def get_all_objects(cls) -> List[str]:
        """Get all objects (resources) in policies"""
        enforcer = cls.get_enforcer()
        return enforcer.get_all_objects()

    @classmethod
    def get_all_actions(cls) -> List[str]:
        """Get all actions in policies"""
        enforcer = cls.get_enforcer()
        return enforcer.get_all_actions()

    @classmethod
    def get_all_roles(cls) -> List[str]:
        """Get all role names"""
        enforcer = cls.get_enforcer()
        return enforcer.get_all_roles()

    @classmethod
    def get_policy_count(cls) -> dict:
        """Get count of policies and role assignments"""
        enforcer = cls.get_enforcer()
        return {
            "policies": len(enforcer.get_policy()),
            "role_assignments": len(enforcer.get_grouping_policy()),
            "total": len(enforcer.get_policy()) + len(enforcer.get_grouping_policy())
        }
