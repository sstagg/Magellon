"""
Criteria Parser Service

Parses  criteria expressions from sys_sec_object_permission.Criteria
and converts them to Casbin resource identifiers.

This completes the TODO in casbin_policy_sync_service.py line 308:
"Complex criteria-based permissions will need additional application-layer filtering"

Author: Magellon Development Team
Created: 2025-11-04
"""
import re
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class CriteriaParserService:
    """
    Service to parse  criteria expressions into Casbin-compatible resources.

    Supported Criteria Formats:
    1. Simple session ID: `[session_id] = 'uuid'` or `[oid] = 'uuid'`
    2. Multiple sessions: `[session_id] IN ('uuid1', 'uuid2')`
    3. User-based: `[user_id] = CurrentUserId()`
    4. Owner check: `[owner_id] = CurrentUserId()`

    Output: List of Casbin resource identifiers like "msession:uuid"
    """

    # UUID regex pattern
    UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

    @staticmethod
    def parse_criteria(
        criteria: str,
        target_type: str,
        user_id: Optional[UUID] = None
    ) -> List[str]:
        """
        Parse criteria string into list of Casbin resource identifiers.

        Args:
            criteria:  criteria expression (e.g., "[session_id] = 'uuid'")
            target_type: Target type from sys_sec_type_permission (e.g., "Image", "Msession")
            user_id: Current user ID for dynamic expressions like CurrentUserId()

        Returns:
            List of Casbin resource identifiers (e.g., ["msession:uuid1", "msession:uuid2"])
            Empty list if criteria can't be parsed or is too complex

        Examples:
            >>> parse_criteria("[session_id] = 'abc-123'", "Image")
            ["msession:abc-123"]

            >>> parse_criteria("[oid] IN ('uuid1', 'uuid2')", "Msession")
            ["msession:uuid1", "msession:uuid2"]

            >>> parse_criteria("[user_id] = CurrentUserId()", "Msession", user_id=UUID(...))
            ["msession:*"]  # User-specific, needs special handling
        """
        if not criteria or not criteria.strip():
            return []

        criteria = criteria.strip()

        try:
            # Determine resource prefix based on target type
            resource_prefix = CriteriaParserService._get_resource_prefix(target_type)

            # Pattern 1: Simple equality - [session_id] = 'uuid' or [oid] = 'uuid'
            if "=" in criteria and "IN" not in criteria.upper():
                return CriteriaParserService._parse_simple_equality(
                    criteria, resource_prefix
                )

            # Pattern 2: IN clause - [session_id] IN ('uuid1', 'uuid2')
            elif "IN" in criteria.upper():
                return CriteriaParserService._parse_in_clause(
                    criteria, resource_prefix
                )

            # Pattern 3: CurrentUserId() - Dynamic user-based filter
            elif "CurrentUserId()" in criteria or "CurrentUser()" in criteria:
                return CriteriaParserService._parse_user_based(
                    criteria, resource_prefix, user_id
                )

            # Pattern 4: Complex criteria - Cannot convert to Casbin
            else:
                logger.warning(f"Complex criteria not supported for Casbin sync: {criteria}")
                return []

        except Exception as e:
            logger.error(f"Error parsing criteria '{criteria}': {e}")
            return []

    @staticmethod
    def _get_resource_prefix(target_type: str) -> str:
        """
        Get Casbin resource prefix from target type.

        Args:
            target_type: From sys_sec_type_permission.TargetType

        Returns:
            Resource prefix for Casbin (e.g., "msession", "image")
        """
        # Map  type names to resource prefixes
        type_mapping = {
            "Image": "image",
            "Msession": "msession",
            "Session": "msession",  # Alias
            "Camera": "camera",
            "Microscope": "microscope",
            "Project": "project",
            "User": "user"
        }

        return type_mapping.get(target_type, target_type.lower())

    @staticmethod
    def _parse_simple_equality(criteria: str, resource_prefix: str) -> List[str]:
        """
        Parse simple equality: [session_id] = 'uuid' or [oid] = 'uuid'

        Returns:
            List with single resource identifier
        """
        # Extract UUIDs from criteria
        uuids = re.findall(CriteriaParserService.UUID_PATTERN, criteria, re.IGNORECASE)

        if uuids:
            # Use first UUID found
            return [f"{resource_prefix}:{uuids[0]}"]

        return []

    @staticmethod
    def _parse_in_clause(criteria: str, resource_prefix: str) -> List[str]:
        """
        Parse IN clause: [session_id] IN ('uuid1', 'uuid2', ...)

        Returns:
            List of resource identifiers for each UUID
        """
        # Extract all UUIDs from IN clause
        uuids = re.findall(CriteriaParserService.UUID_PATTERN, criteria, re.IGNORECASE)

        if uuids:
            return [f"{resource_prefix}:{uuid}" for uuid in uuids]

        return []

    @staticmethod
    def _parse_user_based(
        criteria: str,
        resource_prefix: str,
        user_id: Optional[UUID]
    ) -> List[str]:
        """
        Parse user-based criteria: [user_id] = CurrentUserId()

        This is more complex because it's dynamic per user.
        Options:
        1. Create user-specific policies (adds many policies to Casbin)
        2. Return wildcard and handle in application layer
        3. Use Casbin ABAC (Attribute-Based Access Control)

        For now: Return special marker for application-layer handling

        Returns:
            Special marker or empty list
        """
        # Check what field is being filtered
        if "[user_id]" in criteria or "[owner_id]" in criteria:
            # This means: "user can only see records where user_id/owner_id = their ID"
            # This is too dynamic for simple Casbin policies
            # Return special marker for application layer
            logger.info(f"User-based criteria detected: {criteria}")
            logger.info("  -> Will be handled in application layer with SQL filtering")
            return [f"{resource_prefix}:*:user-owned"]  # Special marker

        # Check if specific UUIDs are mentioned (mixed criteria)
        uuids = re.findall(CriteriaParserService.UUID_PATTERN, criteria, re.IGNORECASE)
        if uuids:
            return [f"{resource_prefix}:{uuid}" for uuid in uuids]

        return []

    @staticmethod
    def can_sync_to_casbin(criteria: str) -> bool:
        """
        Check if criteria can be synced to Casbin policies.

        Criteria that CAN be synced:
        - Simple equality: [session_id] = 'uuid'
        - IN clauses: [session_id] IN ('uuid1', 'uuid2')

        Criteria that CANNOT be synced:
        - Dynamic user filters: [user_id] = CurrentUserId()
        - Complex AND/OR: [a] = 'x' AND [b] = 'y'
        - Computed fields: [status] = 'active'

        Args:
            criteria: Criteria string to check

        Returns:
            True if can be synced to Casbin, False if needs application-layer handling
        """
        if not criteria:
            return False

        # Can sync: Simple equality or IN clause with UUIDs
        has_uuids = bool(re.search(CriteriaParserService.UUID_PATTERN, criteria))
        is_simple = ("=" in criteria or "IN" in criteria.upper())
        no_dynamic = "CurrentUserId()" not in criteria and "CurrentUser()" not in criteria

        return has_uuids and is_simple and no_dynamic

    @staticmethod
    def parse_and_categorize(
        criteria: str,
        target_type: str
    ) -> Dict[str, any]:
        """
        Parse criteria and categorize how it should be handled.

        Args:
            criteria: Criteria string
            target_type: Target type

        Returns:
            Dictionary with:
            - can_sync_to_casbin: bool
            - resources: List[str] (Casbin resources if syncable)
            - handling: "casbin" | "application_layer" | "hybrid"
            - complexity: "simple" | "complex"
        """
        result = {
            "can_sync_to_casbin": False,
            "resources": [],
            "handling": "unknown",
            "complexity": "unknown",
            "original_criteria": criteria
        }

        if not criteria:
            return result

        # Check if can sync
        can_sync = CriteriaParserService.can_sync_to_casbin(criteria)
        result["can_sync_to_casbin"] = can_sync

        if can_sync:
            # Parse into resources
            resources = CriteriaParserService.parse_criteria(criteria, target_type)
            result["resources"] = resources
            result["handling"] = "casbin"
            result["complexity"] = "simple"

        elif "CurrentUserId()" in criteria:
            # User-based filtering - needs hybrid approach
            result["handling"] = "hybrid"
            result["complexity"] = "dynamic"
            result["resources"] = []  # Can't pre-compute

        else:
            # Complex criteria - application layer only
            result["handling"] = "application_layer"
            result["complexity"] = "complex"
            result["resources"] = []

        return result


class CasbinResourceBuilder:
    """
    Helper class to build Casbin resource identifiers.

    Follows the pattern: {resource_type}:{resource_id}
    Examples:
    - msession:abc-123
    - image:def-456
    - project:*
    """

    @staticmethod
    def build_session_resource(session_id: UUID) -> str:
        """Build resource identifier for session."""
        return f"msession:{session_id}"

    @staticmethod
    def build_image_resource(image_id: UUID) -> str:
        """Build resource identifier for image."""
        return f"image:{image_id}"

    @staticmethod
    def build_project_resource(project_id: UUID) -> str:
        """Build resource identifier for project."""
        return f"project:{project_id}"

    @staticmethod
    def build_wildcard_resource(resource_type: str) -> str:
        """Build wildcard resource for type-level permissions."""
        return f"{resource_type.lower()}:*"

    @staticmethod
    def parse_resource(resource: str) -> Tuple[str, str]:
        """
        Parse resource identifier back into type and ID.

        Args:
            resource: Resource identifier (e.g., "msession:abc-123")

        Returns:
            Tuple of (resource_type, resource_id)
        """
        if ":" in resource:
            parts = resource.split(":", 1)
            return (parts[0], parts[1])
        return (resource, "*")

    @staticmethod
    def is_wildcard(resource: str) -> bool:
        """Check if resource is a wildcard (type-level)."""
        return resource.endswith(":*")

    @staticmethod
    def is_instance_resource(resource: str) -> bool:
        """Check if resource is instance-level (specific ID)."""
        return ":" in resource and not resource.endswith(":*")


# Export main classes
__all__ = [
    'CriteriaParserService',
    'CasbinResourceBuilder'
]
