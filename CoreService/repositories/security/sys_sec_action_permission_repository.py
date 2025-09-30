"""
Repository for sys_sec_action_permission table operations
"""
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


class SysSecActionPermissionRepository:
    """Repository for managing action permissions"""

    @staticmethod
    def create(db: Session, role_id: UUID, action_id: str):
        """
        Create an action permission for a role
        """
        try:
            # Check if permission already exists
            existing = SysSecActionPermissionRepository.fetch_by_role_and_action(
                db, role_id, action_id
            )
            if existing:
                return existing

            from sqlalchemy import text
            insert_query = text("""
                INSERT INTO sys_sec_action_permission ("Oid", "ActionId", "Role", "OptimisticLockField")
                VALUES (:oid, :action_id, :role_id, 0)
                RETURNING "Oid", "ActionId", "Role", "OptimisticLockField"
            """)

            result = db.execute(insert_query, {
                "oid": uuid4(),
                "action_id": action_id,
                "role_id": role_id
            })

            db.commit()
            row = result.fetchone()

            return {
                "oid": row[0],
                "action_id": row[1],
                "role_id": row[2],
                "OptimisticLockField": row[3]
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error creating action permission")
            raise e

    @staticmethod
    def fetch_by_role_and_action(db: Session, role_id: UUID, action_id: str):
        """
        Fetch action permission by role and action ID
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "ActionId", "Role", "OptimisticLockField"
            FROM sys_sec_action_permission
            WHERE "Role" = :role_id AND "ActionId" = :action_id
        """)

        result = db.execute(query, {
            "role_id": role_id,
            "action_id": action_id
        })
        row = result.fetchone()

        if row is None:
            return None

        return {
            "oid": row[0],
            "action_id": row[1],
            "role_id": row[2],
            "OptimisticLockField": row[3]
        }

    @staticmethod
    def fetch_by_role(db: Session, role_id: UUID):
        """
        Fetch all action permissions for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "ActionId", "Role", "OptimisticLockField"
            FROM sys_sec_action_permission
            WHERE "Role" = :role_id
            ORDER BY "ActionId"
        """)

        result = db.execute(query, {"role_id": role_id})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "action_id": row[1],
                "role_id": row[2],
                "OptimisticLockField": row[3]
            }
            for row in rows
        ]

    @staticmethod
    def fetch_by_action(db: Session, action_id: str):
        """
        Fetch all roles that have permission for a specific action
        """
        from sqlalchemy import text
        query = text("""
            SELECT 
                ap."Oid",
                ap."ActionId",
                ap."Role",
                ap."OptimisticLockField",
                r."Name" as role_name,
                r."IsAdministrative"
            FROM sys_sec_action_permission ap
            JOIN sys_sec_role r ON ap."Role" = r."Oid"
            WHERE ap."ActionId" = :action_id AND r."GCRecord" IS NULL
            ORDER BY r."Name"
        """)

        result = db.execute(query, {"action_id": action_id})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "action_id": row[1],
                "role_id": row[2],
                "OptimisticLockField": row[3],
                "role_name": row[4],
                "is_administrative": row[5]
            }
            for row in rows
        ]

    @staticmethod
    def delete(db: Session, permission_id: UUID):
        """
        Delete an action permission
        """
        try:
            from sqlalchemy import text
            query = text('DELETE FROM sys_sec_action_permission WHERE "Oid" = :permission_id')

            db.execute(query, {"permission_id": permission_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting action permission")
            raise e

    @staticmethod
    def delete_by_role_and_action(db: Session, role_id: UUID, action_id: str):
        """
        Delete action permission by role and action
        """
        try:
            from sqlalchemy import text
            query = text("""
                DELETE FROM sys_sec_action_permission
                WHERE "Role" = :role_id AND "ActionId" = :action_id
            """)

            db.execute(query, {
                "role_id": role_id,
                "action_id": action_id
            })
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting action permission")
            raise e

    @staticmethod
    def delete_all_for_role(db: Session, role_id: UUID):
        """
        Delete all action permissions for a role
        """
        try:
            from sqlalchemy import text
            query = text('DELETE FROM sys_sec_action_permission WHERE "Role" = :role_id')

            db.execute(query, {"role_id": role_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting role permissions")
            raise e

    @staticmethod
    def bulk_create(db: Session, role_id: UUID, action_ids: List[str]):
        """
        Create multiple action permissions for a role
        """
        try:
            from sqlalchemy import text
            
            # Get existing permissions to avoid duplicates
            existing_query = text("""
                SELECT "ActionId" FROM sys_sec_action_permission
                WHERE "Role" = :role_id AND "ActionId" = ANY(:action_ids)
            """)
            result = db.execute(existing_query, {
                "role_id": role_id,
                "action_ids": action_ids
            })
            existing_actions = {row[0] for row in result.fetchall()}

            # Filter out existing permissions
            new_action_ids = [aid for aid in action_ids if aid not in existing_actions]

            if not new_action_ids:
                return []

            # Insert new permissions
            insert_query = text("""
                INSERT INTO sys_sec_action_permission ("Oid", "ActionId", "Role", "OptimisticLockField")
                VALUES (:oid, :action_id, :role_id, 0)
            """)

            created_count = 0
            for action_id in new_action_ids:
                db.execute(insert_query, {
                    "oid": uuid4(),
                    "action_id": action_id,
                    "role_id": role_id
                })
                created_count += 1

            db.commit()
            return new_action_ids

        except Exception as e:
            db.rollback()
            logger.exception("Error in bulk create action permissions")
            raise e

    @staticmethod
    def fetch_all_actions(db: Session):
        """
        Fetch all distinct action IDs from the system
        """
        from sqlalchemy import text
        query = text("""
            SELECT DISTINCT "ActionId"
            FROM sys_sec_action_permission
            ORDER BY "ActionId"
        """)

        result = db.execute(query)
        rows = result.fetchall()

        return [row[0] for row in rows]

    @staticmethod
    def count_permissions_for_role(db: Session, role_id: UUID) -> int:
        """
        Count action permissions for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT COUNT(*)
            FROM sys_sec_action_permission
            WHERE "Role" = :role_id
        """)

        result = db.execute(query, {"role_id": role_id})
        return result.scalar()
