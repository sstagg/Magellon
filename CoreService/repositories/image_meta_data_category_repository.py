import uuid

from sqlalchemy.orm import Session

from models.pydantic_models import ImageMetaDataCategoryDto
from models.sqlalchemy_models import ImageMetaDataCategory
from repositories.base_repository import BaseRepository


class _ImageMetaDataCategoryRepository(BaseRepository[ImageMetaDataCategory]):

    def __init__(self):
        super().__init__(ImageMetaDataCategory)

    async def create(self, db: Session, image_meta_data_category_dto: ImageMetaDataCategoryDto) -> ImageMetaDataCategory:
        if image_meta_data_category_dto.oid is None:
            image_meta_data_category_dto.oid = str(uuid.uuid4())
        entity = ImageMetaDataCategory(
            oid=image_meta_data_category_dto.oid,
            name=image_meta_data_category_dto.name,
        )
        return await super().create(db, entity)

    async def update(self, db: Session, image_meta_data_category_dto) -> None:
        await super().update(db, image_meta_data_category_dto)


ImageMetaDataCategoryRepository = _ImageMetaDataCategoryRepository()
