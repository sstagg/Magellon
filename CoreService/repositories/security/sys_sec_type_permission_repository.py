"""
Repository for sys_sec_type_permission table operations
"""
from typing import List, Optional, Dict
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

import logging

logger = logging.getLogger(__name__)


class SysSecTypePermissionRepository:
    """Repository for managing type/object permissions"""

    @staticmethod
    def create(
        db: Session,
        role_id: UUID,
        target_type: str,
        read_state: int = 0,
        write_state: int = 0,
        create_state: int = 0,
        delete_state: int = 0,
        navigate_state: int = 0
    ):
        """
        Create a type permission for a role
        States: 0 = Deny, 1 = Allow
        """
        try:
            # Check if permission already exists
            existing = SysSecTypePermissionRepository.fetch_by_role_and_type(
                db, role_id, target_type
            )
            if existing:
                return existing

            from sqlalchemy import text
            insert_query = text("""
                INSERT INTO sys_sec_type_permission 
                ("Oid", "TargetType", "Role", "ReadState", "WriteState", "CreateState", 
                 "DeleteState", "NavigateState", "OptimisticLockField")
                VALUES (:oid, :target_type, :role_id, :read_state, :write_state, :create_state,
                        :delete_state, :navigate_state, 0)
                RETURNING "Oid", "TargetType", "Role", "ReadState", "WriteState", "CreateState",
                          "DeleteState", "NavigateState", "OptimisticLockField"
            """)

            result = db.execute(insert_query, {
                "oid": uuid4(),
                "target_type": target_type,
                "role_id": role_id,
                "read_state": read_state,
                "write_state": write_state,
                "create_state": create_state,
                "delete_state": delete_state,
                "navigate_state": navigate_state
            })

            db.commit()
            row = result.fetchone()

            return {
                "oid": row[0],
                "target_type": row[1],
                "role_id": row[2],
                "read_state": row[3],
                "write_state": row[4],
                "create_state": row[5],
                "delete_state": row[6],
                "navigate_state": row[7],
                "OptimisticLockField": row[8]
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error creating type permission")
            raise e

    @staticmethod
    def update(
        db: Session,
        permission_id: UUID,
        read_state: Optional[int] = None,
        write_state: Optional[int] = None,
        create_state: Optional[int] = None,
        delete_state: Optional[int] = None,
        navigate_state: Optional[int] = None
    ):
        """
        Update type permission states
        """
        try:
            # Build update fields dynamically
            update_fields = []
            params = {"permission_id": permission_id}

            if read_state is not None:
                update_fields.append('"ReadState" = :read_state')
                params["read_state"] = read_state

            if write_state is not None:
                update_fields.append('"WriteState" = :write_state')
                params["write_state"] = write_state

            if create_state is not None:
                update_fields.append('"CreateState" = :create_state')
                params["create_state"] = create_state

            if delete_state is not None:
                update_fields.append('"DeleteState" = :delete_state')
                params["delete_state"] = delete_state

            if navigate_state is not None:
                update_fields.append('"NavigateState" = :navigate_state')
                params["navigate_state"] = navigate_state

            if not update_fields:
                return SysSecTypePermissionRepository.fetch_by_id(db, permission_id)

            update_fields.append('"OptimisticLockField" = "OptimisticLockField" + 1')

            from sqlalchemy import text
            update_query = text(f"""
                UPDATE sys_sec_type_permission
                SET {', '.join(update_fields)}
                WHERE "Oid" = :permission_id
                RETURNING "Oid", "TargetType", "Role", "ReadState", "WriteState", "CreateState",
                          "DeleteState", "NavigateState", "OptimisticLockField"
            """)

            result = db.execute(update_query, params)
            db.commit()
            row = result.fetchone()

            if row is None:
                return None

            return {
                "oid": row[0],
                "target_type": row[1],
                "role_id": row[2],
                "read_state": row[3],
                "write_state": row[4],
                "create_state": row[5],
                "delete_state": row[6],
                "navigate_state": row[7],
                "OptimisticLockField": row[8]
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error updating type permission")
            raise e

    @staticmethod
    def fetch_by_id(db: Session, permission_id: UUID):
        """
        Fetch type permission by ID
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "TargetType", "Role", "ReadState", "WriteState", "CreateState",
                   "DeleteState", "NavigateState", "OptimisticLockField"
            FROM sys_sec_type_permission
            WHERE "Oid" = :permission_id
        """)

        result = db.execute(query, {"permission_id": permission_id})
        row = result.fetchone()

        if row is None:
            return None

        return {
            "oid": row[0],
            "target_type": row[1],
            "role_id": row[2],
            "read_state": row[3],
            "write_state": row[4],
            "create_state": row[5],
            "delete_state": row[6],
            "navigate_state": row[7],
            "OptimisticLockField": row[8]
        }

    @staticmethod
    def fetch_by_role_and_type(db: Session, role_id: UUID, target_type: str):
        """
        Fetch type permission by role and target type
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "TargetType", "Role", "ReadState", "WriteState", "CreateState",
                   "DeleteState", "NavigateState", "OptimisticLockField"
            FROM sys_sec_type_permission
            WHERE "Role" = :role_id AND "TargetType" = :target_type
        """)

        result = db.execute(query, {
            "role_id": role_id,
            "target_type": target_type
        })
        row = result.fetchone()

        if row is None:
            return None

        return {
            "oid": row[0],
            "target_type": row[1],
            "role_id": row[2],
            "read_state": row[3],
            "write_state": row[4],
            "create_state": row[5],
            "delete_state": row[6],
            "navigate_state": row[7],
            "OptimisticLockField": row[8]
        }

    @staticmethod
    def fetch_by_role(db: Session, role_id: UUID):
        """
        Fetch all type permissions for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "TargetType", "Role", "ReadState", "WriteState", "CreateState",
                   "DeleteState", "NavigateState", "OptimisticLockField"
            FROM sys_sec_type_permission
            WHERE "Role" = :role_id
            ORDER BY "TargetType"
        """)

        result = db.execute(query, {"role_id": role_id})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "target_type": row[1],
                "role_id": row[2],
                "read_state": row[3],
                "write_state": row[4],
                "create_state": row[5],
                "delete_state": row[6],
                "navigate_state": row[7],
                "OptimisticLockField": row[8]
            }
            for row in rows
        ]

    @staticmethod
    def fetch_by_type(db: Session, target_type: str):
        """
        Fetch all roles that have permissions for a specific type
        """
        from sqlalchemy import text
        query = text("""
            SELECT 
                tp."Oid",
                tp."TargetType",
                tp."Role",
                tp."ReadState",
                tp."WriteState",
                tp."CreateState",
                tp."DeleteState",
                tp."NavigateState",
                tp."OptimisticLockField",
                r."Name" as role_name,
                r."IsAdministrative"
            FROM sys_sec_type_permission tp
            JOIN sys_sec_role r ON tp."Role" = r."Oid"
            WHERE tp."TargetType" = :target_type AND r."GCRecord" IS NULL
            ORDER BY r."Name"
        """)

        result = db.execute(query, {"target_type": target_type})
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "target_type": row[1],
                "role_id": row[2],
                "read_state": row[3],
                "write_state": row[4],
                "create_state": row[5],
                "delete_state": row[6],
                "navigate_state": row[7],
                "OptimisticLockField": row[8],
                "role_name": row[9],
                "is_administrative": row[10]
            }
            for row in rows
        ]

    @staticmethod
    def delete(db: Session, permission_id: UUID):
        """
        Delete a type permission
        """
        try:
            from sqlalchemy import text
            query = text('DELETE FROM sys_sec_type_permission WHERE "Oid" = :permission_id')

            db.execute(query, {"permission_id": permission_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting type permission")
            raise e

    @staticmethod
    def delete_by_role_and_type(db: Session, role_id: UUID, target_type: str):
        """
        Delete type permission by role and type
        """
        try:
            from sqlalchemy import text
            query = text("""
                DELETE FROM sys_sec_type_permission
                WHERE "Role" = :role_id AND "TargetType" = :target_type
            """)

            db.execute(query, {
                "role_id": role_id,
                "target_type": target_type
            })
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting type permission")
            raise e

    @staticmethod
    def delete_all_for_role(db: Session, role_id: UUID):
        """
        Delete all type permissions for a role
        """
        try:
            from sqlalchemy import text
            query = text('DELETE FROM sys_sec_type_permission WHERE "Role" = :role_id')

            db.execute(query, {"role_id": role_id})
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting role type permissions")
            raise e

    @staticmethod
    def fetch_all_types(db: Session):
        """
        Fetch all distinct target types from the system
        """
        from sqlalchemy import text
        query = text("""
            SELECT DISTINCT "TargetType"
            FROM sys_sec_type_permission
            ORDER BY "TargetType"
        """)

        result = db.execute(query)
        rows = result.fetchall()

        return [row[0] for row in rows]

    @staticmethod
    def count_permissions_for_role(db: Session, role_id: UUID) -> int:
        """
        Count type permissions for a role
        """
        from sqlalchemy import text
        query = text("""
            SELECT COUNT(*)
            FROM sys_sec_type_permission
            WHERE "Role" = :role_id
        """)

        result = db.execute(query, {"role_id": role_id})
        return result.scalar()

    @staticmethod
    def grant_full_access(db: Session, role_id: UUID, target_type: str):
        """
        Grant full access (all operations) for a type to a role
        """
        return SysSecTypePermissionRepository.create(
            db, role_id, target_type,
            read_state=1,
            write_state=1,
            create_state=1,
            delete_state=1,
            navigate_state=1
        )

    @staticmethod
    def grant_read_only(db: Session, role_id: UUID, target_type: str):
        """
        Grant read-only access for a type to a role
        """
        return SysSecTypePermissionRepository.create(
            db, role_id, target_type,
            read_state=1,
            write_state=0,
            create_state=0,
            delete_state=0,
            navigate_state=1
        )
