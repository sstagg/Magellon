"""
Repository for sys_sec_user_role table operations (User-Role associations)
"""
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import and_, or_, func, select
from sqlalchemy.orm import Session, joinedload

from models.sqlalchemy_models import SysSecUserRole, SysSecUser, SysSecRole
import logging

logger = logging.getLogger(__name__)


class SysSecUserRoleRepository:
    """Repository for managing user-role associations"""

    @staticmethod
    def assign_role_to_user(db: Session, user_id: UUID, role_id: UUID) -> SysSecUserRole:
        """
        Assign a role to a user
        """
        try:
            # Check if assignment already exists
            existing = SysSecUserRoleRepository.fetch_by_user_and_role(db, user_id, role_id)
            if existing:
                return existing

            user_role = SysSecUserRole(
                oid=uuid4(),
                People=user_id,
                Roles=role_id,
                OptimisticLockField=0
            )

            db.add(user_role)
            db.commit()
            db.refresh(user_role)
            return user_role

        except Exception as e:
            db.rollback()
            logger.exception("Error assigning role to user")
            raise e

    @staticmethod
    def remove_role_from_user(db: Session, user_id: UUID, role_id: UUID) -> bool:
        """
        Remove a role from a user
        """
        try:
            user_role = db.query(SysSecUserRole).filter(
                and_(
                    SysSecUserRole.People == user_id,
                    SysSecUserRole.Roles == role_id
                )
            ).first()

            if not user_role:
                return False

            db.delete(user_role)
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error removing role from user")
            raise e

    @staticmethod
    def fetch_by_user_and_role(db: Session, user_id: UUID, role_id: UUID) -> Optional[SysSecUserRole]:
        """
        Fetch user-role association by user ID and role ID
        """
        return db.query(SysSecUserRole).filter(
            and_(
                SysSecUserRole.People == user_id,
                SysSecUserRole.Roles == role_id
            )
        ).first()

    @staticmethod
    def fetch_roles_by_user(db: Session, user_id: UUID) -> List[SysSecUserRole]:
        """
        Fetch all roles assigned to a user with role details
        """
        return db.query(SysSecUserRole).options(
            joinedload(SysSecUserRole.sys_sec_role)
        ).join(
            SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
        ).filter(
            and_(
                SysSecUserRole.People == user_id,
                SysSecRole.GCRecord.is_(None)
            )
        ).order_by(SysSecRole.Name).all()

    @staticmethod
    def fetch_users_by_role(db: Session, role_id: UUID) -> List[SysSecUserRole]:
        """
        Fetch all users assigned to a role with user details
        """
        return db.query(SysSecUserRole).options(
            joinedload(SysSecUserRole.sys_sec_user)
        ).join(
            SysSecUser, SysSecUserRole.People == SysSecUser.oid
        ).filter(
            and_(
                SysSecUserRole.Roles == role_id,
                SysSecUser.deleted_date.is_(None)
            )
        ).order_by(SysSecUser.USERNAME).all()

    @staticmethod
    def fetch_all_user_roles(db: Session, skip: int = 0, limit: int = 100) -> List[SysSecUserRole]:
        """
        Fetch all user-role associations with details
        """
        return db.query(SysSecUserRole).options(
            joinedload(SysSecUserRole.sys_sec_user),
            joinedload(SysSecUserRole.sys_sec_role)
        ).join(
            SysSecUser, SysSecUserRole.People == SysSecUser.oid
        ).join(
            SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
        ).filter(
            and_(
                SysSecUser.deleted_date.is_(None),
                SysSecRole.GCRecord.is_(None)
            )
        ).order_by(SysSecUser.USERNAME, SysSecRole.Name).offset(skip).limit(limit).all()

    @staticmethod
    def remove_all_user_roles(db: Session, user_id: UUID) -> bool:
        """
        Remove all roles from a user
        """
        try:
            db.query(SysSecUserRole).filter(
                SysSecUserRole.People == user_id
            ).delete()
            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Error removing all user roles")
            raise e

    @staticmethod
    def remove_all_role_assignments(db: Session, role_id: UUID) -> bool:
        """
        Remove a role from all users
        """
        try:
            db.query(SysSecUserRole).filter(
                SysSecUserRole.Roles == role_id
            ).delete()
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
        count = db.query(SysSecUserRole).join(
            SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
        ).filter(
            and_(
                SysSecUserRole.People == user_id,
                SysSecRole.Name == role_name,
                SysSecRole.GCRecord.is_(None)
            )
        ).count()
        return count > 0

    @staticmethod
    def user_has_any_administrative_role(db: Session, user_id: UUID) -> bool:
        """
        Check if a user has any administrative role
        """
        count = db.query(SysSecUserRole).join(
            SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
        ).filter(
            and_(
                SysSecUserRole.People == user_id,
                SysSecRole.IsAdministrative == True,
                SysSecRole.GCRecord.is_(None)
            )
        ).count()
        return count > 0

    @staticmethod
    def count_users_in_role(db: Session, role_id: UUID) -> int:
        """
        Count number of users assigned to a role
        """
        return db.query(SysSecUserRole).join(
            SysSecUser, SysSecUserRole.People == SysSecUser.oid
        ).filter(
            and_(
                SysSecUserRole.Roles == role_id,
                SysSecUser.deleted_date.is_(None)
            )
        ).count()

    @staticmethod
    def count_roles_for_user(db: Session, user_id: UUID) -> int:
        """
        Count number of roles assigned to a user
        """
        return db.query(SysSecUserRole).join(
            SysSecRole, SysSecUserRole.Roles == SysSecRole.Oid
        ).filter(
            and_(
                SysSecUserRole.People == user_id,
                SysSecRole.GCRecord.is_(None)
            )
        ).count()

    @staticmethod
    def bulk_assign_roles(db: Session, user_ids: List[UUID], role_id: UUID) -> List[UUID]:
        """
        Assign a role to multiple users
        """
        try:
            # Get existing assignments to avoid duplicates
            existing_users = {
                ur.People for ur in db.query(SysSecUserRole).filter(
                    and_(
                        SysSecUserRole.People.in_(user_ids),
                        SysSecUserRole.Roles == role_id
                    )
                ).all()
            }

            # Filter out users who already have the role
            new_user_ids = [uid for uid in user_ids if uid not in existing_users]

            if not new_user_ids:
                return []

            # Bulk insert
            new_assignments = [
                SysSecUserRole(
                    oid=uuid4(),
                    People=user_id,
                    Roles=role_id,
                    OptimisticLockField=0
                )
                for user_id in new_user_ids
            ]

            db.add_all(new_assignments)
            db.commit()
            return new_user_ids

        except Exception as e:
            db.rollback()
            logger.exception("Error in bulk role assignment")
            raise e

    @staticmethod
    def sync_user_roles(db: Session, user_id: UUID, role_ids: List[UUID]) -> dict:
        """
        Synchronize user roles - remove existing roles not in list, add new ones
        """
        try:
            # Get current roles
            current_roles = {
                ur.Roles for ur in db.query(SysSecUserRole).filter(
                    SysSecUserRole.People == user_id
                ).all()
            }

            # Determine roles to add and remove
            roles_to_add = set(role_ids) - current_roles
            roles_to_remove = current_roles - set(role_ids)

            # Remove roles
            if roles_to_remove:
                db.query(SysSecUserRole).filter(
                    and_(
                        SysSecUserRole.People == user_id,
                        SysSecUserRole.Roles.in_(roles_to_remove)
                    )
                ).delete(synchronize_session=False)

            # Add roles
            if roles_to_add:
                new_assignments = [
                    SysSecUserRole(
                        oid=uuid4(),
                        People=user_id,
                        Roles=role_id,
                        OptimisticLockField=0
                    )
                    for role_id in roles_to_add
                ]
                db.add_all(new_assignments)

            db.commit()
            return {
                "added": len(roles_to_add),
                "removed": len(roles_to_remove)
            }

        except Exception as e:
            db.rollback()
            logger.exception("Error syncing user roles")
            raise e
