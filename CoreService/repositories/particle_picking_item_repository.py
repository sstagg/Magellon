import uuid
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.pydantic_models import ParticlepickingjobitemDto
from models.sqlalchemy_models import  Image


class ParticlepickingjobitemRepository:

    async def create(db: Session, ppji_dto: ParticlepickingjobitemDto):
        if ppji_dto.Oid is None:
            ppji_dto.Oid = str(uuid.uuid4())
        ppji_dto = Particlepickingjobitem(Oid=ppji_dto.Oid)
        db.add(ppji_dto)
        db.commit()
        db.refresh(ppji_dto)
        return ppji_dto

    def fetch_by_id(db: Session, _id: UUID):
        return db.query(Particlepickingjobitem).filter(Particlepickingjobitem.oid == _id).first()

    def fetch_by_image_name(db: Session, image_name: str):
        particlepickingjobitems = db.query(Particlepickingjobitem).join(Image).filter(Image.name == image_name).all()
        if not particlepickingjobitems:
            raise HTTPException(status_code=404, detail="No Particlepickingjobitems found for Image")
        return particlepickingjobitems

    def fetch_by_image_id(db: Session, _id: UUID):
        return db.query(Particlepickingjobitem).filter(Particlepickingjobitem.image == _id).first()

    def fetch_all(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Particlepickingjobitem).offset(skip).limit(limit).all()

    async def delete(db: Session, _id: UUID):
        db_ppji = db.query(Particlepickingjobitem).filter_by(Oid=_id).first()
        db.delete(db_ppji)
        db.commit()

    async def update(db: Session, ppji_dto: ParticlepickingjobitemDto):
        db.merge(ppji_dto)
        db.commit()

    async def update_by_data(db: Session, _id: UUID, req_body: str):
        try:
            db_item = db.query(Particlepickingjobitem).filter(Particlepickingjobitem.oid == _id).first()
            if not db_item:
                raise HTTPException(status_code=404, detail="Particle picking job item not found")
            db_item.data = req_body
            db.commit()
            db.refresh(db_item)
        except Exception as e:
            db.rollback()
