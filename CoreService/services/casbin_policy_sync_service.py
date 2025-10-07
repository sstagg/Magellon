"""
Casbin Policy Synchronization Service

Syncs policies from sys_sec_* tables to Casbin.
This keeps your existing security tables as the source of truth
while using Casbin for enforcement.
"""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from typing import List, Dict
from uuid import UUID
import logging

from models.sqlalchemy_models import (
    SysSecUser,
    SysSecRole,
    SysSecUserRole,
    SysSecActionPermission,
    SysSecNavigationPermission,
    SysSecTypePermission,
    SysSecObjectPermission,
    SysSecMemberPermission
)
from services.casbin_service import CasbinService

logger = logging.getLogger(__name__)


class CasbinPolicySyncService:
    """Service to sync policies from sys_sec_* tables to Casbin"""

    @staticmethod
    def sync_all_policies(db: Session, clear_existing: bool = True) -> Dict[str, int]:
        """
        Complete sync of all policies from database to Casbin

        This should be run:
        - On application startup
        - After bulk permission changes
        - During migrations

        Args:
            db: SQLAlchemy database session
            clear_existing: If True, clears existing Casbin policies before syncing

        Returns:
            Dictionary with sync statistics
        """
        logger.info("=" * 70)
        logger.info("Starting full policy sync from sys_sec_* tables to Casbin")
        logger.info("=" * 70)

        stats = {
            "user_roles": 0,
            "action_permissions": 0,
            "navigation_permissions": 0,
            "type_permissions": 0,
            "object_permissions": 0,
            "total_policies": 0,
            "errors": 0
        }

        try:
            # Clear existing Casbin policies if requested
            if clear_existing:
                CasbinService.clear_policy()
                logger.info("[OK] Cleared existing Casbin policies")

            # Sync in order
            stats["user_roles"] = CasbinPolicySyncService.sync_user_roles(db)
            stats["action_permissions"] = CasbinPolicySyncService.sync_action_permissions(db)
            stats["navigation_permissions"] = CasbinPolicySyncService.sync_navigation_permissions(db)
            stats["type_permissions"] = CasbinPolicySyncService.sync_type_permissions(db)
            stats["object_permissions"] = CasbinPolicySyncService.sync_object_permissions(db)

            # Calculate total
            stats["total_policies"] = (
                stats["action_permissions"] +
                stats["navigation_permissions"] +
                stats["type_permissions"] +
                stats["object_permissions"]
            )

            # Save all policies
            CasbinService.save_policy()

            logger.info("=" * 70)
            logger.info("[OK] Full policy sync completed successfully")
            logger.info(f"  - User-Role assignments: {stats['user_roles']}")
            logger.info(f"  - Action permissions: {stats['action_permissions']}")
            logger.info(f"  - Navigation permissions: {stats['navigation_permissions']}")
            logger.info(f"  - Type permissions: {stats['type_permissions']}")
            logger.info(f"  - Object permissions: {stats['object_permissions']}")
            logger.info(f"  - Total policies: {stats['total_policies']}")
            logger.info("=" * 70)

            return stats

        except Exception as e:
            stats["errors"] = 1
            logger.error(f"[ERROR] Policy sync failed: {e}")
            logger.exception(e)
            raise

    @staticmethod
    def sync_user_roles(db: Session) -> int:
        """
        Sync user-role assignments to Casbin

        Maps: sys_sec_user_role -> Casbin grouping policy (g)

        Returns:
            Number of role assignments synced
        """
        logger.info("Syncing user-role assignments...")

        try:
            user_roles = db.query(SysSecUserRole).options(
                joinedload(SysSecUserRole.sys_sec_user),
                joinedload(SysSecUserRole.sys_sec_role)
            ).all()

            count = 0
            skipped = 0

            for ur in user_roles:
                # Skip if role is soft-deleted
                if ur.sys_sec_role and ur.sys_sec_role.GCRecord is None:
                    user_id = str(ur.People)
                    role_name = ur.sys_sec_role.Name

                    # Add role assignment to Casbin
                    CasbinService.add_role_for_user(user_id, role_name)
                    count += 1
                else:
                    skipped += 1

            logger.info(f"[OK] Synced {count} user-role assignments (skipped {skipped} deleted)")
            return count

        except Exception as e:
            logger.error(f"[ERROR] Error syncing user roles: {e}")
            raise

    @staticmethod
    def sync_action_permissions(db: Session) -> int:
        """
        Sync action permissions to Casbin

        Maps: sys_sec_action_permission -> Casbin policy (p)
        Resource format: "action:{ActionId}"
        Action: "execute"

        Returns:
            Number of action permissions synced
        """
        logger.info("Syncing action permissions...")

        try:
            action_perms = db.query(SysSecActionPermission).options(
                joinedload(SysSecActionPermission.sys_sec_role)
            ).filter(
                SysSecActionPermission.GCRecord.is_(None)
            ).all()

            count = 0
            skipped = 0

            for perm in action_perms:
                if perm.sys_sec_role and perm.sys_sec_role.GCRecord is None:
                    role_name = perm.sys_sec_role.Name
                    resource = f"action:{perm.ActionId}"
                    action = "execute"

                    # Add permission to Casbin
                    CasbinService.add_permission_for_role(role_name, resource, action, "allow")
                    count += 1
                else:
                    skipped += 1

            logger.info(f"[OK] Synced {count} action permissions (skipped {skipped})")
            return count

        except Exception as e:
            logger.error(f"[ERROR] Error syncing action permissions: {e}")
            raise

    @staticmethod
    def sync_navigation_permissions(db: Session) -> int:
        """
        Sync navigation permissions to Casbin

        Maps: sys_sec_navigation_permission -> Casbin policy (p)
        Resource format: "navigation:{ItemPath}"
        Action: "navigate"
        Effect: Based on NavigateState (0=deny, 1=allow)

        Returns:
            Number of navigation permissions synced
        """
        logger.info("Syncing navigation permissions...")

        try:
            nav_perms = db.query(SysSecNavigationPermission).options(
                joinedload(SysSecNavigationPermission.sys_sec_role)
            ).filter(
                SysSecNavigationPermission.GCRecord.is_(None)
            ).all()

            count = 0
            skipped = 0

            for perm in nav_perms:
                if perm.sys_sec_role and perm.sys_sec_role.GCRecord is None:
                    role_name = perm.sys_sec_role.Name
                    resource = f"navigation:{perm.ItemPath}"
                    action = "navigate"
                    effect = "allow" if perm.NavigateState == 1 else "deny"

                    # Add permission to Casbin
                    CasbinService.add_permission_for_role(role_name, resource, action, effect)
                    count += 1
                else:
                    skipped += 1

            logger.info(f"[OK] Synced {count} navigation permissions (skipped {skipped})")
            return count

        except Exception as e:
            logger.error(f"[ERROR] Error syncing navigation permissions: {e}")
            raise

    @staticmethod
    def sync_type_permissions(db: Session) -> int:
        """
        Sync type permissions to Casbin

        Maps: sys_sec_type_permission -> Casbin policies (p)
        Resource format: "{TargetType}:*" for all instances of that type
        Actions: read, write, create, delete, navigate
        Effect: Based on state fields (0=no permission, 1=allow)

        Returns:
            Number of type permission operations synced
        """
        logger.info("Syncing type permissions...")

        try:
            type_perms = db.query(SysSecTypePermission).options(
                joinedload(SysSecTypePermission.sys_sec_role)
            ).filter(
                SysSecTypePermission.GCRecord.is_(None)
            ).all()

            count = 0
            skipped_perms = 0
            skipped_ops = 0

            for perm in type_perms:
                if perm.sys_sec_role and perm.sys_sec_role.GCRecord is None:
                    role_name = perm.sys_sec_role.Name
                    resource = f"{perm.TargetType}:*"

                    # Add policy for each CRUD operation that is allowed
                    operations_added = 0

                    if perm.ReadState == 1:
                        CasbinService.add_permission_for_role(role_name, resource, "read", "allow")
                        operations_added += 1

                    if perm.WriteState == 1:
                        CasbinService.add_permission_for_role(role_name, resource, "write", "allow")
                        operations_added += 1

                    if perm.CreateState == 1:
                        CasbinService.add_permission_for_role(role_name, resource, "create", "allow")
                        operations_added += 1

                    if perm.DeleteState == 1:
                        CasbinService.add_permission_for_role(role_name, resource, "delete", "allow")
                        operations_added += 1

                    if perm.NavigateState == 1:
                        CasbinService.add_permission_for_role(role_name, resource, "navigate", "allow")
                        operations_added += 1

                    if operations_added > 0:
                        count += operations_added
                    else:
                        skipped_ops += 1

                else:
                    skipped_perms += 1

            logger.info(f"[OK] Synced {count} type permission operations (skipped {skipped_perms} perms, {skipped_ops} with no ops)")
            return count

        except Exception as e:
            logger.error(f"[ERROR] Error syncing type permissions: {e}")
            raise

    @staticmethod
    def sync_object_permissions(db: Session) -> int:
        """
        Sync object-level permissions to Casbin

        NOTE: This handles simple object permissions.
        Complex criteria-based permissions will need additional application-layer filtering.

        For now, we log object permissions but handle them in application layer
        because they have criteria that need parsing.

        Returns:
            Number of object permissions logged (not synced to Casbin yet)
        """
        logger.info("Syncing object permissions...")

        try:
            obj_perms = db.query(SysSecObjectPermission).options(
                joinedload(SysSecObjectPermission.sys_sec_type_permission).joinedload(
                    SysSecTypePermission.sys_sec_role
                )
            ).filter(
                SysSecObjectPermission.GCRecord.is_(None)
            ).all()

            count = len(obj_perms)

            if count > 0:
                logger.info(f"[WARNING] Found {count} object permissions with criteria")
                logger.info("  -> Object permissions will be handled in application layer")
                logger.info("  -> They require criteria parsing (e.g., 'owner_id = CurrentUserId()')")
                logger.info("  -> Use PermissionService.filter_by_object_permissions() for query filtering")

                # Log a few examples
                for i, perm in enumerate(obj_perms[:3]):
                    if perm.sys_sec_type_permission and perm.sys_sec_type_permission.sys_sec_role:
                        role_name = perm.sys_sec_type_permission.sys_sec_role.Name
                        target_type = perm.sys_sec_type_permission.TargetType
                        criteria = perm.Criteria or "None"
                        logger.debug(f"  Example {i+1}: Role={role_name}, Type={target_type}, Criteria={criteria}")

            else:
                logger.info("[OK] No object permissions found")

            return 0  # Not synced to Casbin yet

        except Exception as e:
            logger.error(f"[ERROR] Error checking object permissions: {e}")
            raise

    @staticmethod
    def sync_user_permissions(db: Session, user_id: UUID) -> int:
        """
        Sync permissions for a specific user

        Use this when:
        - User roles change
        - User is created/updated

        Args:
            db: Database session
            user_id: User UUID to sync

        Returns:
            Number of roles synced for user
        """
        logger.info(f"Syncing permissions for user {user_id}...")

        try:
            user_id_str = str(user_id)

            # Remove existing roles for user in Casbin
            CasbinService.delete_roles_for_user(user_id_str)

            # Re-sync roles
            user_roles = db.query(SysSecUserRole).options(
                joinedload(SysSecUserRole.sys_sec_role)
            ).filter(
                SysSecUserRole.People == user_id
            ).all()

            count = 0
            for ur in user_roles:
                if ur.sys_sec_role and ur.sys_sec_role.GCRecord is None:
                    CasbinService.add_role_for_user(user_id_str, ur.sys_sec_role.Name)
                    count += 1

            logger.info(f"[OK] Synced {count} roles for user {user_id}")
            return count

        except Exception as e:
            logger.error(f"[ERROR] Error syncing user {user_id} permissions: {e}")
            raise

    @staticmethod
    def sync_role_permissions(db: Session, role_id: UUID) -> Dict[str, int]:
        """
        Sync all permissions for a specific role

        Use this when:
        - Role permissions change
        - Role is created/updated

        NOTE: This is complex because we'd need to remove only policies for this role
        without affecting other roles. For now, recommend doing a full sync after role changes.

        Args:
            db: Database session
            role_id: Role UUID to sync

        Returns:
            Dictionary with counts of permissions synced
        """
        logger.info(f"Syncing permissions for role {role_id}...")

        stats = {
            "action_permissions": 0,
            "navigation_permissions": 0,
            "type_permissions": 0
        }

        try:
            role = db.query(SysSecRole).filter(SysSecRole.Oid == role_id).first()
            if not role:
                logger.warning(f"Role {role_id} not found")
                return stats

            if role.GCRecord is not None:
                logger.warning(f"Role {role_id} is soft-deleted")
                return stats

            role_name = role.Name

            # Note: Casbin doesn't have a direct "remove all policies for role" method
            # We'd need to get all policies, filter by role, and remove each one
            # For now, we'll just add new policies (duplicates are ignored by Casbin)

            # Sync action permissions
            action_perms = db.query(SysSecActionPermission).filter(
                and_(
                    SysSecActionPermission.Role == role_id,
                    SysSecActionPermission.GCRecord.is_(None)
                )
            ).all()

            for perm in action_perms:
                resource = f"action:{perm.ActionId}"
                CasbinService.add_permission_for_role(role_name, resource, "execute", "allow")
                stats["action_permissions"] += 1

            # Sync navigation permissions
            nav_perms = db.query(SysSecNavigationPermission).filter(
                and_(
                    SysSecNavigationPermission.Role == role_id,
                    SysSecNavigationPermission.GCRecord.is_(None)
                )
            ).all()

            for perm in nav_perms:
                resource = f"navigation:{perm.ItemPath}"
                effect = "allow" if perm.NavigateState == 1 else "deny"
                CasbinService.add_permission_for_role(role_name, resource, "navigate", effect)
                stats["navigation_permissions"] += 1

            # Sync type permissions
            type_perms = db.query(SysSecTypePermission).filter(
                and_(
                    SysSecTypePermission.Role == role_id,
                    SysSecTypePermission.GCRecord.is_(None)
                )
            ).all()

            for perm in type_perms:
                resource = f"{perm.TargetType}:*"

                if perm.ReadState == 1:
                    CasbinService.add_permission_for_role(role_name, resource, "read", "allow")
                    stats["type_permissions"] += 1

                if perm.WriteState == 1:
                    CasbinService.add_permission_for_role(role_name, resource, "write", "allow")
                    stats["type_permissions"] += 1

                if perm.CreateState == 1:
                    CasbinService.add_permission_for_role(role_name, resource, "create", "allow")
                    stats["type_permissions"] += 1

                if perm.DeleteState == 1:
                    CasbinService.add_permission_for_role(role_name, resource, "delete", "allow")
                    stats["type_permissions"] += 1

                if perm.NavigateState == 1:
                    CasbinService.add_permission_for_role(role_name, resource, "navigate", "allow")
                    stats["type_permissions"] += 1

            total = stats["action_permissions"] + stats["navigation_permissions"] + stats["type_permissions"]
            logger.info(f"[OK] Synced {total} permissions for role {role_id}")
            logger.info(f"  - Actions: {stats['action_permissions']}")
            logger.info(f"  - Navigation: {stats['navigation_permissions']}")
            logger.info(f"  - Type ops: {stats['type_permissions']}")

            return stats

        except Exception as e:
            logger.error(f"[ERROR] Error syncing role {role_id} permissions: {e}")
            raise

    @staticmethod
    def verify_sync(db: Session) -> Dict[str, any]:
        """
        Verify that Casbin policies match sys_sec_* tables

        Returns:
            Dictionary with verification results
        """
        logger.info("Verifying policy sync...")

        results = {
            "user_roles_match": False,
            "expected_user_roles": 0,
            "actual_user_roles": 0,
            "expected_policies": 0,
            "actual_policies": 0,
            "discrepancies": []
        }

        try:
            # Count expected user roles
            expected_user_roles = db.query(SysSecUserRole).join(
                SysSecRole
            ).filter(
                SysSecRole.GCRecord.is_(None)
            ).count()

            # Count actual user roles in Casbin
            actual_user_roles = len(CasbinService.get_grouping_policy())

            results["expected_user_roles"] = expected_user_roles
            results["actual_user_roles"] = actual_user_roles
            results["user_roles_match"] = expected_user_roles == actual_user_roles

            # Count expected policies
            action_count = db.query(SysSecActionPermission).filter(
                SysSecActionPermission.GCRecord.is_(None)
            ).count()

            nav_count = db.query(SysSecNavigationPermission).filter(
                SysSecNavigationPermission.GCRecord.is_(None)
            ).count()

            # Type permissions generate multiple policies (one per CRUD operation)
            type_perms = db.query(SysSecTypePermission).filter(
                SysSecTypePermission.GCRecord.is_(None)
            ).all()

            type_ops_count = sum([
                (1 if tp.ReadState == 1 else 0) +
                (1 if tp.WriteState == 1 else 0) +
                (1 if tp.CreateState == 1 else 0) +
                (1 if tp.DeleteState == 1 else 0) +
                (1 if tp.NavigateState == 1 else 0)
                for tp in type_perms
            ])

            expected_policies = action_count + nav_count + type_ops_count

            # Count actual policies in Casbin
            actual_policies = len(CasbinService.get_policy())

            results["expected_policies"] = expected_policies
            results["actual_policies"] = actual_policies

            # Check for discrepancies
            if results["user_roles_match"]:
                logger.info(f"[OK] User roles match: {actual_user_roles}")
            else:
                discrepancy = f"User roles mismatch: expected {expected_user_roles}, got {actual_user_roles}"
                results["discrepancies"].append(discrepancy)
                logger.warning(f"[WARNING] {discrepancy}")

            if expected_policies == actual_policies:
                logger.info(f"[OK] Policies match: {actual_policies}")
            else:
                discrepancy = f"Policies mismatch: expected {expected_policies}, got {actual_policies}"
                results["discrepancies"].append(discrepancy)
                logger.warning(f"[WARNING] {discrepancy}")

            if len(results["discrepancies"]) == 0:
                logger.info("[OK] Sync verification passed!")
            else:
                logger.warning(f"[WARNING] Found {len(results['discrepancies'])} discrepancies")

            return results

        except Exception as e:
            logger.error(f"[ERROR] Error verifying sync: {e}")
            raise
