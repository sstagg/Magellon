import uuid

from sqlalchemy.orm import Session

from models.pydantic_models import SessionDto
from models.sqlalchemy_models import Msession
from repositories.base_repository import BaseRepository


class _SessionRepository(BaseRepository[Msession]):

    def __init__(self):
        super().__init__(Msession)

    async def create(self, db: Session, session_dto: SessionDto) -> Msession:
        if session_dto.oid is None:
            session_dto.oid = str(uuid.uuid4())
        session_instance = Msession(oid=session_dto.oid, name=session_dto.name)
        return await super().create(db, session_instance)

    async def update(self, db: Session, session_dto) -> None:
        await super().update(db, session_dto)


SessionRepository = _SessionRepository()
