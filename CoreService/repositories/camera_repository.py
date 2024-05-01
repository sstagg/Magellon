import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from models.pydantic_models import CameraDto
from models.sqlalchemy_models import Camera


class CameraRepository:

    async def create(db: Session, camera_dto: CameraDto):
        if camera_dto.oid is None:
            camera_dto.oid = str(uuid.uuid4())
        camera = Camera(oid=camera_dto.oid, name=camera_dto.name)
        db.add(camera)
        db.commit()
        db.refresh(camera)
        return camera

    def fetch_by_id(db: Session, _id: UUID):
        return db.query(Camera).filter(Camera.oid == _id).first()

    def fetch_by_name(db: Session, name: str):
        return db.query(Camera).filter(Camera.name == name).first()

    def fetch_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Camera).offset(skip).limit(limit).all()

    async def delete(db: Session, _id: UUID):
        db_camera = db.query(Camera).filter_by(oid=_id).first()
        db.delete(db_camera)
        db.commit()

    async def update(db: Session, camera_dto):
        db.merge(camera_dto)
        db.commit()
