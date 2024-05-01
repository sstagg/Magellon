import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from models.pydantic_models import SessionDto
from models.sqlalchemy_models import Msession


class SessionRepository:

    async def create(self, db: Session, session_dto: SessionDto):
        if session_dto.oid is None:
            session_dto.oid = str(uuid.uuid4())
        session_instance = Msession(oid=session_dto.oid, name=session_dto.name)
        db.add(session_instance)
        db.commit()
        db.refresh(session_instance)
        return session_instance

    def fetch_by_id(db: Session, _id: UUID):
        return db.query(Msession).filter(Msession.Oid == _id).first()

    def fetch_by_name(db: Session, name: str):
        return db.query(Msession).filter(Msession.name == name).first()

    def fetch_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Msession).offset(skip).limit(limit).all()

    async def delete(db: Session, _id: UUID):
        db_Session = db.query(Msession).filter_by(Oid=_id).first()
        db.delete(db_Session)
        db.commit()

    async def update(db: Session, Session_dto):
        db.merge(Session_dto)
        db.commit()
