"""
SQLAlchemy Row-Level Security Middleware

Automatically filters queries based on Casbin permissions.
Works transparently - no need to modify existing endpoints!

Based on industry best practices:
- Uses session.info for user context (standard SQLAlchemy pattern)
- Global event listener on Session class
- Compatible with FastAPI dependency injection
- Supports multi-tenancy and row-level permissions

Usage:
    from core.sqlalchemy_row_level_security import apply_row_level_security

    # In your endpoint
    db = get_db()
    apply_row_level_security(db, current_user_id)

    # Now ALL queries automatically filter by accessible sessions
    images = db.query(Image).all()  # Only returns accessible images!

References:
- https://theshubhendra.medium.com/role-based-row-filtering-advanced-sqlalchemy-techniques-733e6b1328f6
- https://docs.sqlalchemy.org/en/20/orm/events.html#do-orm-execute
"""

from typing import Optional, List, Set
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import event, inspect
from sqlalchemy.sql import Select

from services.casbin_service import CasbinService

# Flag to track if global event listener is registered
_event_listener_registered = False


class RowLevelSecurityFilter:
    """
    SQLAlchemy event listener that automatically adds WHERE clauses
    to filter queries based on Casbin permissions.
    """

    # Tables that should be filtered by session access
    FILTERED_TABLES = {
        'Image': 'session_id',        # Filter Image by session_id
        'Movie': 'session_id',        # Filter Movie by session_id
        'Particle': 'session_id',     # Filter Particle by session_id
        'Atlas': 'session_id',        # Filter Atlas by session_id
        'Square': 'session_id',       # Filter Square by session_id
        'Hole': 'session_id',         # Filter Hole by session_id
        'Msession': 'oid',            # Filter Msession by oid (itself)
        # Add more tables as needed
    }

    @classmethod
    def apply_filter(cls, session: Session, user_id: UUID):
        """
        Apply row-level security filter to this session.

        All queries on filtered tables will automatically be restricted
        to accessible sessions for this user.

        Uses session.info to store user context - this is the standard
        SQLAlchemy pattern for passing data to event listeners.

        Args:
            session: SQLAlchemy session
            user_id: Current user's UUID
        """
        # Get accessible sessions for this user
        accessible_sessions = cls._get_accessible_sessions(user_id)

        # Store in session.info (standard SQLAlchemy pattern)
        session.info['rls_enabled'] = True
        session.info['user_id'] = str(user_id)
        session.info['accessible_sessions'] = accessible_sessions

        # Register global event listener (only once)
        cls._register_event_listener()

    @classmethod
    def _get_accessible_sessions(cls, user_id: UUID) -> Set[str]:
        """
        Get set of session IDs that user can access via Casbin.

        Returns:
            Set of session UUIDs as strings, or {'*'} for wildcard access
        """
        user_id_str = str(user_id)

        # Get user's roles
        roles = CasbinService.get_roles_for_user(user_id_str)

        # Get all Casbin policies
        policies = CasbinService.get_policy()

        accessible = set()

        for policy in policies:
            role, resource, action, effect = policy

            # Check if this policy applies to user's roles
            if role in roles and effect == "allow" and action in ("read", "*"):
                # Parse resource identifier
                if resource.startswith("msession:"):
                    if resource == "msession:*":
                        # Wildcard access - user can access ALL sessions
                        return {'*'}
                    else:
                        # Specific session
                        session_id = resource.split(":", 1)[1]
                        accessible.add(session_id)

        return accessible

    @classmethod
    def _register_event_listener(cls):
        """
        Register global event listener for do_orm_execute.

        This is registered once globally and checks session.info
        to determine if filtering should be applied.
        """
        global _event_listener_registered

        if _event_listener_registered:
            return

        @event.listens_for(Session, "do_orm_execute")
        def _filter_query(execute_state):
            """
            Event handler that intercepts query execution and adds WHERE filters.

            This is called by SQLAlchemy before executing any query.
            Checks execute_state.session.info for RLS context.
            """
            # Check if RLS is enabled for this session
            if not execute_state.session.info.get('rls_enabled', False):
                return

            # Get accessible sessions from session.info
            accessible_sessions = execute_state.session.info.get('accessible_sessions')

            if accessible_sessions is None:
                # No accessible sessions defined
                return

            if '*' in accessible_sessions:
                # User has wildcard access - don't filter
                return

            # Only process SELECT statements
            if not execute_state.is_select:
                return

            # Get the query statement
            statement = execute_state.statement

            # Only process if it's a Select statement
            if not isinstance(statement, Select):
                return

            # Check if query involves any filtered tables
            # Use froms to get table references
            if hasattr(statement, 'column_descriptions'):
                for mapper in statement.column_descriptions:
                    entity = mapper.get('entity')
                    if entity is None:
                        continue

                    table_name = entity.__name__
                    if table_name not in cls.FILTERED_TABLES:
                        continue

                    # Apply filter based on table type
                    filter_column = cls.FILTERED_TABLES[table_name]

                    if table_name == 'Msession':
                        # Filter Msession by oid (primary key)
                        if accessible_sessions:
                            statement = statement.where(
                                entity.oid.in_(accessible_sessions)
                            )
                        else:
                            # No accessible sessions - return empty result
                            statement = statement.where(entity.oid.in_([]))
                    else:
                        # Filter other tables by session_id (foreign key)
                        if accessible_sessions:
                            statement = statement.where(
                                getattr(entity, filter_column).in_(accessible_sessions)
                            )
                        else:
                            # No accessible sessions - return empty result
                            statement = statement.where(
                                getattr(entity, filter_column).in_([])
                            )

                    # Replace the statement with filtered version
                    execute_state.statement = statement

        _event_listener_registered = True


def apply_row_level_security(db: Session, user_id: UUID):
    """
    Enable row-level security filtering for this database session.

    After calling this, all queries will automatically be filtered
    to only return data the user has access to via Casbin.

    Usage in FastAPI endpoint:
        @router.get('/images/')
        def get_images(
            db: Session = Depends(get_db),
            user_id: UUID = Depends(get_current_user_id)
        ):
            # Enable RLS
            apply_row_level_security(db, user_id)

            # This query is automatically filtered!
            images = db.query(Image).all()  # Only accessible images
            return images

    Args:
        db: SQLAlchemy session
        user_id: Current user's UUID
    """
    RowLevelSecurityFilter.apply_filter(db, user_id)


def get_accessible_sessions_for_user(user_id: UUID) -> List[str]:
    """
    Get list of session IDs that user can access.

    Useful for manual filtering or checking access.

    Args:
        user_id: User's UUID

    Returns:
        List of session UUID strings, or ['*'] for wildcard access
    """
    accessible = RowLevelSecurityFilter._get_accessible_sessions(user_id)
    return list(accessible)


def check_session_access(user_id: UUID, session_id: UUID, action: str = "read") -> bool:
    """
    Check if user has access to specific session.

    Args:
        user_id: User's UUID
        session_id: Session UUID
        action: Action to check (read/write/delete)

    Returns:
        True if user has access, False otherwise
    """
    user_id_str = str(user_id)
    resource = f"msession:{session_id}"
    return CasbinService.enforce(user_id_str, resource, action)


def get_session_filter_clause(user_id: UUID, column_name: str = "session_id") -> tuple:
    """
    Get SQL WHERE clause and parameters for session filtering.

    Use this with raw SQL queries (text()) to manually add RLS filtering.

    Args:
        user_id: Current user's UUID
        column_name: Name of the session_id column (default: "session_id")

    Returns:
        tuple: (where_clause, parameters_dict)

    Example:
        # In your endpoint
        clause, params = get_session_filter_clause(user_id)

        # Add to your SQL query
        query = text(f'''
            SELECT * FROM image
            WHERE GCRecord IS NULL
            {clause}  -- Adds: AND session_id IN :accessible_sessions
        ''')

        # Execute with merged parameters
        result = db.execute(query, {**your_params, **params})

    Example with custom column name:
        # For msession table (filter by oid instead of session_id)
        clause, params = get_session_filter_clause(user_id, column_name="oid")

        query = text(f'''
            SELECT * FROM msession
            WHERE GCRecord IS NULL
            {clause}  -- Adds: AND oid IN :accessible_sessions
        ''')
    """
    accessible_sessions = RowLevelSecurityFilter._get_accessible_sessions(user_id)

    if '*' in accessible_sessions:
        # Admin with wildcard access - no filtering needed
        return ("", {})

    if not accessible_sessions:
        # No access - return impossible condition (empty tuple)
        # This ensures the query returns 0 rows
        return (
            f"AND {column_name} IN :accessible_sessions",
            {"accessible_sessions": tuple()}  # Empty tuple = no matches
        )

    # Normal case - filter by accessible sessions
    # Convert UUIDs to tuple for SQL IN clause
    return (
        f"AND {column_name} IN :accessible_sessions",
        {"accessible_sessions": tuple(accessible_sessions)}
    )


# ==================== FastAPI Dependency ====================

from fastapi import Depends
from dependencies.auth import get_current_user_id
from database import get_db


def get_filtered_db(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)
) -> Session:
    """
    FastAPI dependency that returns a database session with RLS enabled.

    Use this instead of get_db() to automatically filter all queries.

    Usage:
        @router.get('/images/')
        def get_images(db: Session = Depends(get_filtered_db)):
            # All queries automatically filtered by user's permissions!
            images = db.query(Image).all()
            return images
    """
    apply_row_level_security(db, user_id)
    return db
