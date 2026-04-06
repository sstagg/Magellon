import uuid
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions import EntityNotFoundError
from models.pydantic_models import ImageMetaDataDto
from models.sqlalchemy_models import ImageMetaData
from repositories.base_repository import BaseRepository


class _ImageMetaDataRepository(BaseRepository[ImageMetaData]):

    def __init__(self):
        super().__init__(ImageMetaData)

    async def create(self, db: Session, image_meta_data_dto: ImageMetaDataDto) -> ImageMetaData:
        if image_meta_data_dto.oid is None:
            image_meta_data_dto.oid = str(uuid.uuid4())
        entity = ImageMetaData(**image_meta_data_dto.dict())
        return await super().create(db, entity)

    async def update(self, db: Session, oid: UUID = None, image_meta_data_dto: ImageMetaDataDto = None) -> ImageMetaData:
        if oid:
            entity = db.query(ImageMetaData).filter(ImageMetaData.oid == oid).first()
            if entity:
                for key, value in image_meta_data_dto.dict(exclude_unset=True).items():
                    setattr(entity, key, value)
                db.commit()
                db.refresh(entity)
                return entity
            else:
                raise EntityNotFoundError("ImageMetaData", oid)
        else:
            db.merge(image_meta_data_dto)
            db.commit()

    async def update_by_data(self, db: Session, _id: UUID, req_body: str):
        db_item = db.query(ImageMetaData).filter(ImageMetaData.oid == _id).first()
        if not db_item:
            raise EntityNotFoundError("ImageMetaData", oid)
        db_item.data = req_body
        db.commit()
        db.refresh(db_item)


ImageMetaDataRepository = _ImageMetaDataRepository()
