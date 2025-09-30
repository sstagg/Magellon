"""
Repository for sys_sec_user_role table operations (User-Role associations)
"""
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


class SysSecUserRoleRepository:
    """Repository for managing user-role associations"""

    @staticmethod
    def assign_role_to_user(db: Session, user_id: UUID, role_id: UUID):
        """
        Assign a role to a user
        """
        try:
            # Check if assignment already exists
            existing = SysSecUserRoleRepository.fetch_by_user_and_role(db, user_id, role_id)
            if existing:
                return existing

            from sqlalchemy import text
            insert_query = text("""
                INSERT INTO sys_sec_user_role ("OID", "People", "Roles", "OptimisticLockField")
                VALUES (:oid, :user_id, :role_id, 0)
                RETURNING "OID", "People", "Roles", "OptimisticLockField"
            """)

            result = db.execute(insert_query, {
                "oid": uuid4(),
                "user_id": user_id,
                "role_id": role_id
            })

            db.commit()
            row = result.fetchone()

            return {
                "oid": row[0],
                "user_id": row[1],
                "role_id": row[2],
                "OptimisticLockField": row[3]
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error assigning role to user")
            raise e

    @staticmethod
    def remove_role_from_user(db: Session, user_id: UUID, role_id: UUID):
        """
        Remove a role from a user
        """
        try:
            from sqlalchemy import text
            delete_query = text("""
                DELETE FROM sys_sec_user_role
                WHERE "People" = :user_id AND "Roles" = :role_id
            """)

            db.execute(delete_query, {
                "user_id": user_id,
                "role_id": role_id
            })
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error removing role from user")
            raise e

    @staticmethod
    def fetch_by_user_and_role(db: Session, user_id: UUID, role_id: UUID):
        """
        Fetch user-role association by user ID and role ID
        """
        from sqlalchemy import text
        query = text("""
            SELECT "OID", "People", "Roles", "OptimisticLockField"
            FROM sys_sec_user_role
            WHERE "People" = :user_id AND "Roles" = :role_id
        """)

        result = db.execute(query, {
            "user_id": user_id,
            "role_id": role_id
        })
        row = result.fetchone()

        if row is None:
            return None

        return {
            "oid": row[0],
            "user_id": row[1],
            "role_id": row[2],
            "OptimisticLockField": row[3]
        }

    @staticmethod
    def fetch_roles_by_user(db: Session, user_id: UUID):
        """
        Fetch all roles assigned to a user with role details
        """
        from sqlalchemy import text
        query = text("""
            SELECT 
                ur."OID",
                ur."People",
                ur."Roles",
                ur."OptimisticLockField",
                r."Name",
                r."IsAdministrative",
                r."CanEditModel",
                r."PermissionPolicy"
            FROM sys_sec_user_role ur
            JOIN sys_sec_role r ON ur."Roles" = r."Oid"
            WHERE ur."People" = :user_id AND r."GCRecord" IS NULL
            ORDER BY r."Name"
        """)

        result = db.execute(query, {"user_id": user_id})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "user_id": row[1],
                "role_id": row[2],
                "OptimisticLockField": row[3],
                "role_name": row[4],
                "is_administrative": row[5],
                "can_edit_model": row[6],
                "permission_policy": row[7]
            }
            for row in rows
        ]

    @staticmethod
    def fetch_users_by_role(db: Session, role_id: UUID):
        """
        Fetch all users assigned to a role with user details
        """
        from sqlalchemy import text
        query = text("""
            SELECT 
                ur."OID",
                ur."People",
                ur."Roles",
                ur."OptimisticLockField",
                u."username",
                u."active",
                u."email_verification_status",
                u."created_date"
            FROM sys_sec_user_role ur
            JOIN sys_sec_user u ON ur."People" = u.oid
            WHERE ur."Roles" = :role_id 
                AND u.deleted_date IS NULL
            ORDER BY u.username
        """)

        result = db.execute(query, {"role_id": role_id})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "user_id": row[1],
                "role_id": row[2],
                "OptimisticLockField": row[3],
                "username": row[4],
                "active": row[5],
                "email_verification_status": row[6],
                "created_date": row[7]
            }
            for row in rows
        ]

    @staticmethod
    def fetch_all_user_roles(db: Session, skip: int = 0, limit: int = 100):
        """
        Fetch all user-role associations with details
        """
        from sqlalchemy import text
        query = text("""
            SELECT 
                ur."OID",
                ur."People",
                ur."Roles",
                ur."OptimisticLockField",
                u."username",
                r."Name" as role_name,
                r."IsAdministrative",
                r."CanEditModel"
            FROM sys_sec_user_role ur
            JOIN sys_sec_user u ON ur."People" = u.oid
            JOIN sys_sec_role r ON ur."Roles" = r."Oid"
            WHERE u.deleted_date IS NULL AND r."GCRecord" IS NULL
            ORDER BY u.username, r."Name"
            LIMIT :limit OFFSET :skip
        """)

        result = db.execute(query, {"skip": skip, "limit": limit})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "user_id": row[1],
                "role_id": row[2],
                "OptimisticLockField": row[3],
                "username": row[4],
                "role_name": row[5],
                "is_administrative": row[6],
                "can_edit_model": row[7]
            }
            for row in rows
        ]

    @staticmethod
    def remove_all_user_roles(db: Session, user_id: UUID):
        """
        Remove all roles from a user
        """
        try:
            from sqlalchemy import text
            delete_query = text("""
                DELETE FROM sys_sec_user_role
                WHERE "People" = :user_id
            """)

            db.execute(delete_query, {"user_id": user_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error removing all user roles")
            raise e

    @staticmethod
    def remove_all_role_assignments(db: Session, role_id: UUID):
        """
        Remove a role from all users
        """
        try:
            from sqlalchemy import text
            delete_query = text("""
                DELETE FROM sys_sec_user_role
                WHERE "Roles" = :role_id
            """)

            db.execute(delete_query, {"role_id": role_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error removing role from all users")
            raise e

    @staticmethod
    def user_has_role(db: Session, user_id: UUID, role_name: str) -> bool:
        """
        Check if a user has a specific role by role name
        """
        from sqlalchemy import text
        query = text("""
            SELECT COUNT(*)
            FROM sys_sec_user_role ur
            JOIN sys_sec_role r ON ur."Roles" = r."Oid"
            WHERE ur."People" = :user_id 
                AND r."Name" = :role_name 
                AND r."GCRecord" IS NULL
        """)

        result = db.execute(query, {
            "user_id": user_id,
            "role_name": role_name
        })
        count = result.scalar()
        return count > 0

    @staticmethod
    def user_has_any_administrative_role(db: Session, user_id: UUID) -> bool:
        """
        Check if a user has any administrative role
        """
        from sqlalchemy import text
        query = text("""
            SELECT COUNT(*)
            FROM sys_sec_user_role ur
            JOIN sys_sec_role r ON ur."Roles" = r."Oid"
            WHERE ur."People" = :user_id 
                AND r."IsAdministrative" = TRUE 
                AND r."GCRecord" IS NULL
        """)

        result = db.execute(query, {"user_id": user_id})
        count = result.scalar()
        return count > 0

    @staticmethod
    def count_users_in_role(db: Session, role_id: UUID) -> int:
        """
        Count number of users assigned to a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT COUNT(*)
            FROM sys_sec_user_role ur
            JOIN sys_sec_user u ON ur."People" = u.oid
            WHERE ur."Roles" = :role_id AND u.deleted_date IS NULL
        """)

        result = db.execute(query, {"role_id": role_id})
        return result.scalar()

    @staticmethod
    def count_roles_for_user(db: Session, user_id: UUID) -> int:
        """
        Count number of roles assigned to a user
        """
        from sqlalchemy import text
        query = text("""
            SELECT COUNT(*)
            FROM sys_sec_user_role ur
            JOIN sys_sec_role r ON ur."Roles" = r."Oid"
            WHERE ur."People" = :user_id AND r."GCRecord" IS NULL
        """)

        result = db.execute(query, {"user_id": user_id})
        return result.scalar()

    @staticmethod
    def bulk_assign_roles(db: Session, user_ids: List[UUID], role_id: UUID):
        """
        Assign a role to multiple users
        """
        try:
            from sqlalchemy import text
            
            # Get existing assignments to avoid duplicates
            existing_query = text("""
                SELECT "People" FROM sys_sec_user_role
                WHERE "People" = ANY(:user_ids) AND "Roles" = :role_id
            """)
            result = db.execute(existing_query, {
                "user_ids": [str(uid) for uid in user_ids],
                "role_id": role_id
            })
            existing_users = {row[0] for row in result.fetchall()}

            # Filter out users who already have the role
            new_user_ids = [uid for uid in user_ids if uid not in existing_users]

            if not new_user_ids:
                return []

            # Prepare bulk insert data
            values = [(uuid4(), user_id, role_id, 0) for user_id in new_user_ids]
            
            insert_query = text("""
                INSERT INTO sys_sec_user_role ("OID", "People", "Roles", "OptimisticLockField")
                VALUES (:oid, :user_id, :role_id, :lock_field)
            """)

            for val in values:
                db.execute(insert_query, {
                    "oid": val[0],
                    "user_id": val[1],
                    "role_id": val[2],
                    "lock_field": val[3]
                })

            db.commit()
            return new_user_ids

        except Exception as e:
            db.rollback()
            logger.exception("Error in bulk role assignment")
            raise e

    @staticmethod
    def sync_user_roles(db: Session, user_id: UUID, role_ids: List[UUID]):
        """
        Synchronize user roles - remove existing roles not in list, add new ones
        """
        try:
            # Get current roles
            from sqlalchemy import text
            current_query = text("""
                SELECT "Roles" FROM sys_sec_user_role
                WHERE "People" = :user_id
            """)
            result = db.execute(current_query, {"user_id": user_id})
            current_roles = {row[0] for row in result.fetchall()}

            # Determine roles to add and remove
            roles_to_add = set(role_ids) - current_roles
            roles_to_remove = current_roles - set(role_ids)

            # Remove roles
            if roles_to_remove:
                delete_query = text("""
                    DELETE FROM sys_sec_user_role
                    WHERE "People" = :user_id AND "Roles" = ANY(:role_ids)
                """)
                db.execute(delete_query, {
                    "user_id": user_id,
                    "role_ids": [str(rid) for rid in roles_to_remove]
                })

            # Add roles
            if roles_to_add:
                insert_query = text("""
                    INSERT INTO sys_sec_user_role ("OID", "People", "Roles", "OptimisticLockField")
                    VALUES (:oid, :user_id, :role_id, 0)
                """)
                for role_id in roles_to_add:
                    db.execute(insert_query, {
                        "oid": uuid4(),
                        "user_id": user_id,
                        "role_id": role_id
                    })

            db.commit()
            return {
                "added": len(roles_to_add),
                "removed": len(roles_to_remove)
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error syncing user roles")
            raise e
