from uuid import UUID

from sqlalchemy.orm import Session

from models.pydantic_models import PyCamera
from models.sqlalchemy_models import Camera


class CameraRepository:

    async def create(db: Session, camera: PyCamera):
        camera = Camera(name=camera.name)
        db.add(camera)
        db.commit()
        db.refresh(camera)
        return camera

    def fetch_by_id(db: Session, _id: UUID):
        return db.query(Camera).filter(Camera.Oid == _id).first()

    def fetch_by_name(db: Session, name: str):
        return db.query(Camera).filter(Camera.name == name).first()

    def fetch_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Camera).offset(skip).limit(limit).all()

    async def delete(db: Session, _id: int):
        db_store = db.query(Camera).filter_by(id=_id).first()
        db.delete(db_store)
        db.commit()

    async def update(db: Session, store_data):
        db.merge(store_data)
        db.commit()
