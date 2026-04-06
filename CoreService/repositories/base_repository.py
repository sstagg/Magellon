import uuid
from typing import Type, TypeVar, Generic, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic base repository providing common CRUD operations."""

    def __init__(self, model: Type[T], pk_field: str = "oid"):
        self.model = model
        self.pk_field = pk_field

    def _pk_column(self):
        return getattr(self.model, self.pk_field)

    async def create(self, db: Session, entity: T) -> T:
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return entity

    def fetch_by_id(self, db: Session, _id: UUID) -> Optional[T]:
        return db.query(self.model).filter(self._pk_column() == _id).first()

    def fetch_by_name(self, db: Session, name: str) -> Optional[T]:
        return db.query(self.model).filter(self.model.name == name).first()

    def fetch_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[T]:
        return db.query(self.model).offset(skip).limit(limit).all()

    async def delete(self, db: Session, _id: UUID) -> None:
        entity = db.query(self.model).filter(self._pk_column() == _id).first()
        if entity:
            db.delete(entity)
            db.commit()

    async def update(self, db: Session, entity) -> None:
        db.merge(entity)
        db.commit()
