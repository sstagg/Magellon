from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session
from starlette import status
import logging

from database import get_db
# from models.pydantic_models import ParticlepickingjobitemDto
from repositories.particle_picking_item_repository import ParticlepickingjobitemRepository
from dependencies.permissions import require_permission
from dependencies.auth import get_current_user_id

logger = logging.getLogger(__name__)
ppji_router = APIRouter()


@ppji_router.post('/', response_model=ParticlepickingjobitemDto, status_code=201)
async def create_particlepickingjobitem(
    particlepicking_jobitem_request: ParticlepickingjobitemDto,
    db_session: Session = Depends(get_db),
    _: None = Depends(require_permission('particle_picking', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Create a particle picking job item and save it in the database.

    **Requires:** 'create' permission on 'particle_picking' resource
    **Security:** Only users with particle picking creation permission can access
    """
    logger.info(f"User {user_id} creating particle picking job item")

    # Validate input data
    if not particlepicking_jobitem_request.data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Data cannot be empty'
        )

    # Create Particlepickingjobitem in the database
    try:
        created_item = await ParticlepickingjobitemRepository.create(
            db=db_session,
            Particlepickingjobitem_dto=particlepicking_jobitem_request
        )
        logger.info(f"Particle picking job item created by user {user_id}: {created_item.oid}")
        return created_item
    except Exception as e:
        logger.exception(f'Error creating particle picking job item for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating particle picking job item'
        )


@ppji_router.put('/', response_model=ParticlepickingjobitemDto, status_code=201)
async def update_particlepickingjobitem(
    particlepickingjobitem_request: ParticlepickingjobitemDto,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('particle_picking', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Update a particle picking job item and save it in the database.

    **Requires:** 'write' permission on 'particle_picking' resource
    **Security:** Only users with particle picking write permission can access
    """
    logger.info(f"User {user_id} updating particle picking job item: {particlepickingjobitem_request.oid}")
    try:
        updated_item = await ParticlepickingjobitemRepository.update(
            db=db,
            Particlepickingjobitem_dto=particlepickingjobitem_request
        )
        logger.info(f"Particle picking job item updated by user {user_id}: {particlepickingjobitem_request.oid}")
        return updated_item
    except Exception as e:
        logger.exception(f'Error updating particle picking job item for user {user_id}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating particle picking job item'
        )


@ppji_router.get('/', response_model=List[ParticlepickingjobitemDto])
def get_all_particlepickingjobitems(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get all particle picking job items in database.

    **Requires:** Authentication (all authenticated users can read)
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching particle picking job items")
    return ParticlepickingjobitemRepository.fetch_all(db)


@ppji_router.get('/{oid}', response_model=ParticlepickingjobitemDto)
def get_particlepickingjobitem(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get particle picking job item by ID.

    **Requires:** Authentication
    **Security:** User must be authenticated
    """
    logger.debug(f"User {user_id} fetching particle picking job item: {oid}")

    db_particlepickingjobitem = ParticlepickingjobitemRepository.fetch_by_id(db, oid)
    if db_particlepickingjobitem is None:
        raise HTTPException(status_code=404, detail="Particle picking job item not found with the given ID")
    return db_particlepickingjobitem


@ppji_router.delete('/{oid}')
async def delete_particlepickingjobitem(
    oid: UUID,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('particle_picking', 'delete')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Delete particle picking job item by ID.

    **Requires:** 'delete' permission on 'particle_picking' resource
    **Security:** Only users with particle picking delete permission can access
    """
    logger.warning(f"User {user_id} deleting particle picking job item: {oid}")

    db_particlepickingjobitem = ParticlepickingjobitemRepository.fetch_by_id(db, oid)
    if db_particlepickingjobitem is None:
        raise HTTPException(status_code=404, detail="Particle picking job item not found with the given ID")

    await ParticlepickingjobitemRepository.delete(db, oid)
    logger.info(f"Particle picking job item {oid} deleted by user {user_id}")
    return {"message": "Particle picking job item deleted successfully", "deleted_by": str(user_id)}

# @app.get("/Particlepickingjobitems2/", response_model=List[ParticlepickingjobitemDto])
# def show_Particlepickingjobitems(db: Session = Depends(get_db)):
#     records = db.query(Particlepickingjobitem).all()
#     return records
