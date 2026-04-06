import uuid

from sqlalchemy.orm import Session

from models.pydantic_models import CameraDto
from models.sqlalchemy_models import Camera
from repositories.base_repository import BaseRepository


class _CameraRepository(BaseRepository[Camera]):

    def __init__(self):
        super().__init__(Camera)

    async def create(self, db: Session, camera_dto: CameraDto) -> Camera:
        if camera_dto.oid is None:
            camera_dto.oid = str(uuid.uuid4())
        camera = Camera(oid=camera_dto.oid, name=camera_dto.name)
        return await super().create(db, camera)

    async def update(self, db: Session, camera_dto) -> None:
        await super().update(db, camera_dto)


CameraRepository = _CameraRepository()
