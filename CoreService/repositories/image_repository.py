import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from domain.imaging.repositories import ImageRepositoryInterface
from models.pydantic_models import ImageDto
from models.sqlalchemy_models import Image, Msession
from repositories.base_repository import BaseRepository


class _ImageRepository(BaseRepository[Image], ImageRepositoryInterface):

    def __init__(self):
        super().__init__(Image)

    async def create(self, db: Session, image_dto: ImageDto) -> Image:
        if image_dto.Oid is None:
            image_dto.Oid = str(uuid.uuid4())
        image = Image(oid=image_dto.Oid, name=image_dto.name)
        return await super().create(db, image)

    def fetch_all_by_session_name(self, db: Session, session_name: str):
        return db.query(self.model).join(Msession).filter(Msession.name == session_name).all()

    async def update(self, db: Session, image_dto) -> None:
        await super().update(db, image_dto)


ImageRepository = _ImageRepository()
