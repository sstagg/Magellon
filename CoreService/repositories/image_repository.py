import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from models.pydantic_models import ImageDto
from models.sqlalchemy_models import Image


class ImageRepository:

    async def create(db: Session, image_dto: ImageDto):
        if image_dto.Oid is None:
            image_dto.Oid = str(uuid.uuid4())
        image_dto = Image(Oid=image_dto.Oid, name=image_dto.Name)
        db.add(image_dto)
        db.commit()
        db.refresh(image_dto)
        return image_dto

    def fetch_by_id(db: Session, _id: UUID):
        return db.query(Image).filter(Image.Oid == _id).first()

    def fetch_by_name(db: Session, name: str):
        return db.query(Image).filter(Image.Name == name).first()

    def fetch_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Image).offset(skip).limit(limit).all()

    async def delete(db: Session, _id: UUID):
        db_image = db.query(Image).filter_by(Oid=_id).first()
        db.delete(db_image)
        db.commit()

    async def update(db: Session, image_dto):
        db.merge(image_dto)
        db.commit()
