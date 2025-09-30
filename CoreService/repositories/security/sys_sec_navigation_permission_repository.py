"""
Repository for sys_sec_navigation_permission table operations
"""
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


class SysSecNavigationPermissionRepository:
    """Repository for managing navigation permissions"""

    @staticmethod
    def create(db: Session, role_id: UUID, item_path: str, navigate_state: int = 1):
        """
        Create a navigation permission for a role
        navigate_state: 0 = Deny, 1 = Allow
        """
        try:
            # Check if permission already exists
            existing = SysSecNavigationPermissionRepository.fetch_by_role_and_path(
                db, role_id, item_path
            )
            if existing:
                return existing

            from sqlalchemy import text
            insert_query = text("""
                INSERT INTO sys_sec_navigation_permission 
                ("Oid", "ItemPath", "NavigateState", "Role", "OptimisticLockField")
                VALUES (:oid, :item_path, :navigate_state, :role_id, 0)
                RETURNING "Oid", "ItemPath", "NavigateState", "Role", "OptimisticLockField"
            """)

            result = db.execute(insert_query, {
                "oid": uuid4(),
                "item_path": item_path,
                "navigate_state": navigate_state,
                "role_id": role_id
            })

            db.commit()
            row = result.fetchone()

            return {
                "oid": row[0],
                "item_path": row[1],
                "navigate_state": row[2],
                "role_id": row[3],
                "OptimisticLockField": row[4]
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error creating navigation permission")
            raise e

    @staticmethod
    def update(db: Session, permission_id: UUID, navigate_state: int):
        """
        Update navigation state for a permission
        """
        try:
            from sqlalchemy import text
            update_query = text("""
                UPDATE sys_sec_navigation_permission
                SET "NavigateState" = :navigate_state,
                    "OptimisticLockField" = "OptimisticLockField" + 1
                WHERE "Oid" = :permission_id
                RETURNING "Oid", "ItemPath", "NavigateState", "Role", "OptimisticLockField"
            """)

            result = db.execute(update_query, {
                "navigate_state": navigate_state,
                "permission_id": permission_id
            })
            db.commit()
            row = result.fetchone()

            if row is None:
                return None

            return {
                "oid": row[0],
                "item_path": row[1],
                "navigate_state": row[2],
                "role_id": row[3],
                "OptimisticLockField": row[4]
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error updating navigation permission")
            raise e

    @staticmethod
    def fetch_by_role_and_path(db: Session, role_id: UUID, item_path: str):
        """
        Fetch navigation permission by role and path
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "ItemPath", "NavigateState", "Role", "OptimisticLockField"
            FROM sys_sec_navigation_permission
            WHERE "Role" = :role_id AND "ItemPath" = :item_path
        """)

        result = db.execute(query, {
            "role_id": role_id,
            "item_path": item_path
        })
        row = result.fetchone()

        if row is None:
            return None

        return {
            "oid": row[0],
            "item_path": row[1],
            "navigate_state": row[2],
            "role_id": row[3],
            "OptimisticLockField": row[4]
        }

    @staticmethod
    def fetch_by_role(db: Session, role_id: UUID):
        """
        Fetch all navigation permissions for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "ItemPath", "NavigateState", "Role", "OptimisticLockField"
            FROM sys_sec_navigation_permission
            WHERE "Role" = :role_id
            ORDER BY "ItemPath"
        """)

        result = db.execute(query, {"role_id": role_id})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "item_path": row[1],
                "navigate_state": row[2],
                "role_id": row[3],
                "OptimisticLockField": row[4]
            }
            for row in rows
        ]

    @staticmethod
    def fetch_by_path(db: Session, item_path: str):
        """
        Fetch all roles that have permission for a specific path
        """
        from sqlalchemy import text
        query = text("""
            SELECT 
                np."Oid",
                np."ItemPath",
                np."NavigateState",
                np."Role",
                np."OptimisticLockField",
                r."Name" as role_name,
                r."IsAdministrative"
            FROM sys_sec_navigation_permission np
            JOIN sys_sec_role r ON np."Role" = r."Oid"
            WHERE np."ItemPath" = :item_path AND r."GCRecord" IS NULL
            ORDER BY r."Name"
        """)

        result = db.execute(query, {"item_path": item_path})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "item_path": row[1],
                "navigate_state": row[2],
                "role_id": row[3],
                "OptimisticLockField": row[4],
                "role_name": row[5],
                "is_administrative": row[6]
            }
            for row in rows
        ]

    @staticmethod
    def delete(db: Session, permission_id: UUID):
        """
        Delete a navigation permission
        """
        try:
            from sqlalchemy import text
            query = text('DELETE FROM sys_sec_navigation_permission WHERE "Oid" = :permission_id')

            db.execute(query, {"permission_id": permission_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting navigation permission")
            raise e

    @staticmethod
    def delete_by_role_and_path(db: Session, role_id: UUID, item_path: str):
        """
        Delete navigation permission by role and path
        """
        try:
            from sqlalchemy import text
            query = text("""
                DELETE FROM sys_sec_navigation_permission
                WHERE "Role" = :role_id AND "ItemPath" = :item_path
            """)

            db.execute(query, {
                "role_id": role_id,
                "item_path": item_path
            })
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting navigation permission")
            raise e

    @staticmethod
    def delete_all_for_role(db: Session, role_id: UUID):
        """
        Delete all navigation permissions for a role
        """
        try:
            from sqlalchemy import text
            query = text('DELETE FROM sys_sec_navigation_permission WHERE "Role" = :role_id')

            db.execute(query, {"role_id": role_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting role navigation permissions")
            raise e

    @staticmethod
    def bulk_create(db: Session, role_id: UUID, item_paths: List[str], navigate_state: int = 1):
        """
        Create multiple navigation permissions for a role
        """
        try:
            from sqlalchemy import text
            
            # Get existing permissions to avoid duplicates
            existing_query = text("""
                SELECT "ItemPath" FROM sys_sec_navigation_permission
                WHERE "Role" = :role_id AND "ItemPath" = ANY(:item_paths)
            """)
            result = db.execute(existing_query, {
                "role_id": role_id,
                "item_paths": item_paths
            })
            existing_paths = {row[0] for row in result.fetchall()}

            # Filter out existing permissions
            new_paths = [path for path in item_paths if path not in existing_paths]

            if not new_paths:
                return []

            # Insert new permissions
            insert_query = text("""
                INSERT INTO sys_sec_navigation_permission 
                ("Oid", "ItemPath", "NavigateState", "Role", "OptimisticLockField")
                VALUES (:oid, :item_path, :navigate_state, :role_id, 0)
            """)

            for path in new_paths:
                db.execute(insert_query, {
                    "oid": uuid4(),
                    "item_path": path,
                    "navigate_state": navigate_state,
                    "role_id": role_id
                })

            db.commit()
            return new_paths

        except Exception as e:
            db.rollback()
            logger.exception("Error in bulk create navigation permissions")
            raise e

    @staticmethod
    def fetch_all_paths(db: Session):
        """
        Fetch all distinct navigation paths from the system
        """
        from sqlalchemy import text
        query = text("""
            SELECT DISTINCT "ItemPath"
            FROM sys_sec_navigation_permission
            ORDER BY "ItemPath"
        """)

        result = db.execute(query)
        rows = result.fetchall()

        return [row[0] for row in rows]

    @staticmethod
    def count_permissions_for_role(db: Session, role_id: UUID) -> int:
        """
        Count navigation permissions for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT COUNT(*)
            FROM sys_sec_navigation_permission
            WHERE "Role" = :role_id
        """)

        result = db.execute(query, {"role_id": role_id})
        return result.scalar()

    @staticmethod
    def fetch_allowed_paths_for_role(db: Session, role_id: UUID):
        """
        Fetch all allowed navigation paths for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT "ItemPath"
            FROM sys_sec_navigation_permission
            WHERE "Role" = :role_id AND "NavigateState" = 1
            ORDER BY "ItemPath"
        """)

        result = db.execute(query, {"role_id": role_id})
        rows = result.fetchall()

        return [row[0] for row in rows]

    @staticmethod
    def fetch_denied_paths_for_role(db: Session, role_id: UUID):
        """
        Fetch all denied navigation paths for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT "ItemPath"
            FROM sys_sec_navigation_permission
            WHERE "Role" = :role_id AND "NavigateState" = 0
            ORDER BY "ItemPath"
        """)

        result = db.execute(query, {"role_id": role_id})
        rows = result.fetchall()

        return [row[0] for row in rows]
