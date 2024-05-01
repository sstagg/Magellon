from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
# from models.pydantic_models import ParticlepickingjobitemDto

from fastapi import APIRouter
import logging

from repositories.particle_picking_item_repository import ParticlepickingjobitemRepository

logger = logging.getLogger(__name__)

ppji_router = APIRouter()


@ppji_router.post('/', response_model=ParticlepickingjobitemDto, status_code=201)
async def create_particlepickingjobitem(particlepicking_jobitem_request: ParticlepickingjobitemDto,
                                        db_session: Session = Depends(get_db)):
    """
    Create a Particlepickingjobitem and save it in the database
    """
    logger.info("Creating Particlepickingjobitem in database")
    # Validate input data

    if not particlepicking_jobitem_request.data:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='data cannot be empty')
        # Create Particlepickingjobitem in the database
    try:
        created_particlepickingjobitem = await ParticlepickingjobitemRepository.create(db=db_session,
                                                                                       Particlepickingjobitem_dto=particlepicking_jobitem_request)
    except Exception as e:
        logger.exception('Error creating Particlepickingjobitem in database')
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail='Error creating Particlepickingjobitem')

    return created_particlepickingjobitem


@ppji_router.put('/', response_model=ParticlepickingjobitemDto, status_code=201)
async def update_particlepickingjobitem(particlepickingjobitem_request: ParticlepickingjobitemDto,
                                        db: Session = Depends(get_db)):
    """
    Update a Particlepickingjobitem and save it in the database
    """

    return await ParticlepickingjobitemRepository.update(db=db,
                                                         Particlepickingjobitem_dto=particlepickingjobitem_request)


@ppji_router.get('/', response_model=List[ParticlepickingjobitemDto])
def get_all_particlepickingjobitems(db: Session = Depends(get_db)):
    """
    Get all the Particlepickingjobitems Particlepickingjobitemd in database
    """
    return ParticlepickingjobitemRepository.fetch_all(db)


@ppji_router.get('/{oid}', response_model=ParticlepickingjobitemDto)
def get_particlepickingjobitem(oid: UUID, db: Session = Depends(get_db)):
    """
    Get the Particlepickingjobitem with the given ID provided by User Particlepickingjobitemd in database
    """
    db_particlepickingjobitem = ParticlepickingjobitemRepository.fetch_by_id(db, oid)
    if db_particlepickingjobitem is None:
        raise HTTPException(status_code=404, detail="Particlepickingjobitem not found with the given ID")
    return db_particlepickingjobitem


@ppji_router.delete('/{oid}')
async def delete_particlepickingjobitem(oid: UUID, db: Session = Depends(get_db)):
    """
    Delete the Item with the given ID provided by User Particlepickingjobitemd in database
    """
    db_particlepickingjobitem = ParticlepickingjobitemRepository.fetch_by_id(db, oid)
    if db_particlepickingjobitem is None:
        raise HTTPException(status_code=404, detail="Particlepickingjobitem not found with the given ID")
    await ParticlepickingjobitemRepository.delete(db, oid)
    return "Particlepickingjobitem deleted successfully!"

# @app.get("/Particlepickingjobitems2/", response_model=List[ParticlepickingjobitemDto])
# def show_Particlepickingjobitems(db: Session = Depends(get_db)):
#     records = db.query(Particlepickingjobitem).all()
#     return records
