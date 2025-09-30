"""
Repository for sys_sec_role table operations
"""
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session

from models.security.security_models import (
    RoleCreateDto,
    RoleUpdateDto,
    RoleResponseDto
)
import logging

logger = logging.getLogger(__name__)


class SysSecRoleRepository:
    """Repository for managing security roles"""

    @staticmethod
    def create(db: Session, role_dto: RoleCreateDto, created_by: Optional[UUID] = None):
        """
        Create a new role
        """
        try:
            # Create role dictionary
            role_data = {
                "Oid": uuid4(),
                "Name": role_dto.name,
                "IsAdministrative": role_dto.is_administrative,
                "CanEditModel": role_dto.can_edit_model,
                "PermissionPolicy": role_dto.permission_policy,
                "OptimisticLockField": 0,
                "GCRecord": None
            }

            # Execute raw SQL insert
            from sqlalchemy import text
            insert_query = text("""
                INSERT INTO sys_sec_role 
                ("Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy", 
                  "OptimisticLockField", "GCRecord")
                VALUES 
                (:oid, :name, :is_administrative, :can_edit_model, :permission_policy,
                 :tenant_id, :optimistic_lock_field, :gc_record)
                RETURNING "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                           "OptimisticLockField", "GCRecord", "ObjectType"
            """)

            result = db.execute(insert_query, {
                "oid": role_data["Oid"],
                "name": role_data["Name"],
                "is_administrative": role_data["IsAdministrative"],
                "can_edit_model": role_data["CanEditModel"],
                "permission_policy": role_data["PermissionPolicy"],
                "optimistic_lock_field": role_data["OptimisticLockField"],
                "gc_record": role_data["GCRecord"]
            })

            db.commit()
            row = result.fetchone()

            # Convert row to dict
            role_dict = {
                "oid": row[0],
                "name": row[1],
                "is_administrative": row[2],
                "can_edit_model": row[3],
                "permission_policy": row[4],
                "OptimisticLockField": row[6],
                "GCRecord": row[7],
                "ObjectType": row[8]
            }

            return role_dict

        except Exception as e:
            db.rollback()
            logger.exception("Error creating role")
            raise e

    @staticmethod
    def update(db: Session, role_dto: RoleUpdateDto, updated_by: Optional[UUID] = None):
        """
        Update an existing role
        """
        try:
            # Build update fields dynamically
            update_fields = []
            params = {"oid": role_dto.oid}

            if role_dto.name is not None:
                update_fields.append('"Name" = :name')
                params["name"] = role_dto.name

            if role_dto.is_administrative is not None:
                update_fields.append('"IsAdministrative" = :is_administrative')
                params["is_administrative"] = role_dto.is_administrative

            if role_dto.can_edit_model is not None:
                update_fields.append('"CanEditModel" = :can_edit_model')
                params["can_edit_model"] = role_dto.can_edit_model

            if role_dto.permission_policy is not None:
                update_fields.append('"PermissionPolicy" = :permission_policy')
                params["permission_policy"] = role_dto.permission_policy

            if not update_fields:
                # Nothing to update
                return SysSecRoleRepository.fetch_by_id(db, role_dto.oid)

            # Add optimistic lock increment
            update_fields.append('"OptimisticLockField" = "OptimisticLockField" + 1')

            from sqlalchemy import text
            update_query = text(f"""
                UPDATE sys_sec_role
                SET {', '.join(update_fields)}
                WHERE "Oid" = :oid
                RETURNING "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                          "tenant_id", "OptimisticLockField", "GCRecord", "ObjectType"
            """)

            result = db.execute(update_query, params)
            db.commit()
            row = result.fetchone()

            if row is None:
                return None

            role_dict = {
                "oid": row[0],
                "name": row[1],
                "is_administrative": row[2],
                "can_edit_model": row[3],
                "permission_policy": row[4],
                "tenant_id": row[5],
                "OptimisticLockField": row[6],
                "GCRecord": row[7],
                "ObjectType": row[8]
            }

            return role_dict

        except Exception as e:
            db.rollback()
            logger.exception("Error updating role")
            raise e

    @staticmethod
    def fetch_by_id(db: Session, role_id: UUID):
        """
        Fetch role by ID
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                   "tenant_id", "OptimisticLockField", "GCRecord", "ObjectType"
            FROM sys_sec_role
            WHERE "Oid" = :role_id AND "GCRecord" IS NULL
        """)

        result = db.execute(query, {"role_id": role_id})
        row = result.fetchone()

        if row is None:
            return None

        return {
            "oid": row[0],
            "name": row[1],
            "is_administrative": row[2],
            "can_edit_model": row[3],
            "permission_policy": row[4],
            "tenant_id": row[5],
            "OptimisticLockField": row[6],
            "GCRecord": row[7],
            "ObjectType": row[8]
        }

    @staticmethod
    def fetch_by_name(db: Session, name: str):
        """
        Fetch role by name
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                   "tenant_id", "OptimisticLockField", "GCRecord", "ObjectType"
            FROM sys_sec_role
            WHERE "Name" = :name AND "GCRecord" IS NULL
        """)

        result = db.execute(query, {"name": name})
        row = result.fetchone()

        if row is None:
            return None

        return {
            "oid": row[0],
            "name": row[1],
            "is_administrative": row[2],
            "can_edit_model": row[3],
            "permission_policy": row[4],
            "tenant_id": row[5],
            "OptimisticLockField": row[6],
            "GCRecord": row[7],
            "ObjectType": row[8]
        }

    @staticmethod
    def fetch_all(db: Session, skip: int = 0, limit: int = 100, tenant_id: Optional[UUID] = None):
        """
        Fetch all roles with pagination
        """
        from sqlalchemy import text

        if tenant_id:
            query = text("""
                SELECT "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                       "tenant_id", "OptimisticLockField", "GCRecord", "ObjectType"
                FROM sys_sec_role
                WHERE "GCRecord" IS NULL AND ("tenant_id" = :tenant_id OR "tenant_id" IS NULL)
                ORDER BY "Name"
                LIMIT :limit OFFSET :skip
            """)
            params = {"skip": skip, "limit": limit, "tenant_id": tenant_id}
        else:
            query = text("""
                SELECT "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                       "tenant_id", "OptimisticLockField", "GCRecord", "ObjectType"
                FROM sys_sec_role
                WHERE "GCRecord" IS NULL
                ORDER BY "Name"
                LIMIT :limit OFFSET :skip
            """)
            params = {"skip": skip, "limit": limit}

        result = db.execute(query, params)
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "name": row[1],
                "is_administrative": row[2],
                "can_edit_model": row[3],
                "permission_policy": row[4],
                "tenant_id": row[5],
                "OptimisticLockField": row[6],
                "GCRecord": row[7],
                "ObjectType": row[8]
            }
            for row in rows
        ]

    @staticmethod
    def search_by_name(db: Session, name_pattern: str, skip: int = 0, limit: int = 100):
        """
        Search roles by name pattern
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                   "tenant_id", "OptimisticLockField", "GCRecord", "ObjectType"
            FROM sys_sec_role
            WHERE "Name" ILIKE :pattern AND "GCRecord" IS NULL
            ORDER BY "Name"
            LIMIT :limit OFFSET :skip
        """)

        result = db.execute(query, {
            "pattern": f"%{name_pattern}%",
            "skip": skip,
            "limit": limit
        })
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "name": row[1],
                "is_administrative": row[2],
                "can_edit_model": row[3],
                "permission_policy": row[4],
                "tenant_id": row[5],
                "OptimisticLockField": row[6],
                "GCRecord": row[7],
                "ObjectType": row[8]
            }
            for row in rows
        ]

    @staticmethod
    def delete(db: Session, role_id: UUID, hard_delete: bool = False):
        """
        Delete role (soft delete by default)
        """
        try:
            from sqlalchemy import text

            if hard_delete:
                # Hard delete
                query = text('DELETE FROM sys_sec_role WHERE "Oid" = :role_id')
            else:
                # Soft delete
                query = text("""
                    UPDATE sys_sec_role
                    SET "GCRecord" = :gc_record
                    WHERE "Oid" = :role_id
                """)

            db.execute(query, {
                "role_id": role_id,
                "gc_record": 1 if not hard_delete else None
            })
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error deleting role")
            raise e

    @staticmethod
    def count_roles(db: Session, tenant_id: Optional[UUID] = None):
        """
        Count total roles
        """
        from sqlalchemy import text

        if tenant_id:
            query = text("""
                SELECT COUNT(*)
                FROM sys_sec_role
                WHERE "GCRecord" IS NULL AND ("tenant_id" = :tenant_id OR "tenant_id" IS NULL)
            """)
            result = db.execute(query, {"tenant_id": tenant_id})
        else:
            query = text("""
                SELECT COUNT(*)
                FROM sys_sec_role
                WHERE "GCRecord" IS NULL
            """)
            result = db.execute(query)

        return result.scalar()

    @staticmethod
    def fetch_administrative_roles(db: Session):
        """
        Fetch all administrative roles
        """
        from sqlalchemy import text
        query = text("""
            SELECT "Oid", "Name", "IsAdministrative", "CanEditModel", "PermissionPolicy",
                   "tenant_id", "OptimisticLockField", "GCRecord", "ObjectType"
            FROM sys_sec_role
            WHERE "IsAdministrative" = TRUE AND "GCRecord" IS NULL
            ORDER BY "Name"
        """)

        result = db.execute(query)
        rows = result.fetchall()

        return [
            {
                "oid": row[0],
                "name": row[1],
                "is_administrative": row[2],
                "can_edit_model": row[3],
                "permission_policy": row[4],
                "tenant_id": row[5],
                "OptimisticLockField": row[6],
                "GCRecord": row[7],
                "ObjectType": row[8]
            }
            for row in rows
        ]
