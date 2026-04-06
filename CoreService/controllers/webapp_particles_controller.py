import json
import uuid
import logging
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from database import get_db
from models.pydantic_models import ParticlePickingDto
from models.sqlalchemy_models import Image, ImageMetaData
from core.sqlalchemy_row_level_security import check_session_access
from dependencies.auth import get_current_user_id

particles_router = APIRouter()

logger = logging.getLogger(__name__)


@particles_router.post("/particle-pickings", summary="creates particle picking metadata for a given image and returns it",
                    status_code=201)
async def create_particle_picking(
    meta_name: str = Query(...),
    image_name_or_oid: str = Query(...),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Create particle picking metadata for an image.

    **Requires:** Authentication
    **Security:** User must have write access to the image's session
    """
    logger.info(f"User {user_id} creating particle picking metadata: {meta_name} for image: {image_name_or_oid}")

    try:
        try:
            # Attempt to convert image_name_or_oid to UUID
            image_uuid = UUID(image_name_or_oid)
            # If convertible to UUID, search by OID
            image = db.query(Image).filter_by(oid=image_uuid).first()
        except ValueError:
            # If not convertible to UUID, search by filename
            image = db.query(Image).filter_by(name=image_name_or_oid).first()

        if not image:
            return HTTPException(status_code=404, detail="Image not found")

        # ✅ Check session access
        if image.session_id:
            if not check_session_access(user_id, image.session_id, action="write"):
                logger.warning(f"SECURITY: User {user_id} denied particle picking creation for image: {image_name_or_oid}")
                raise HTTPException(status_code=403, detail="Access denied to this image")

    except NoResultFound:
        # db.close()
        return HTTPException(status_code=404, detail="Image not found")

    try:
        # Check if a "manual" Particlepickingjob already exists
        image_meta_data = db.query(ImageMetaData).filter_by(name=meta_name).one()
    except NoResultFound:
        # If it doesn't exist, create a new one
        image_meta_data = ImageMetaData(

            oid=uuid.uuid4(),
            name=meta_name,
            # description="manual job for particle picking",
            created_date=datetime.now(),
            image_id=image.oid,
            type=5
            # msession=image.msession if image.msession is not None else None,
            # Add other necessary fields here
        )
        # if image.msession is not None:
        #     # Include the image's session in the job and item
        #     manual_job.msession = image.msession
        db.add(image_meta_data)
        db.commit()
        db.refresh(image_meta_data)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@particles_router.get('/particle-pickings')
def get_image_particles(
    img_name: str,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get particle picking metadata for an image.

    **Requires:** Authentication
    **Security:** User must have access to the image's session
    """
    logger.debug(f"User {user_id} requesting particle pickings for image: {img_name}")

    # ✅ First check if user has access to this image's session
    db_image = db.query(Image).filter(Image.name == img_name).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="Image not found")

    if db_image.session_id:
        if not check_session_access(user_id, db_image.session_id, action="read"):
            logger.warning(f"SECURITY: User {user_id} denied particle pickings access to image: {img_name}")
            raise HTTPException(status_code=403, detail="Access denied to this image")

    result = db.query(ImageMetaData). \
        join(Image, ImageMetaData.image_id == Image.oid). \
        filter(Image.name == img_name). \
        all()
    if not result:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitems found for Image")
    response = []
    for row in result:
        image_meta_data = row
        response.append(ParticlePickingDto(
            oid=image_meta_data.oid,
            name=image_meta_data.name,
            image_id=image_meta_data.image_id,
            data_json=json.dumps(image_meta_data.data_json),
            # status=particlepickingjobitem.status,
            # type=particlepickingjobitem.type
        ))
    return response




@particles_router.get('/particles/{oid}', summary="gets an image particles json by its unique id")
async def get_image_particle_by_id(
    oid: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get particle picking data by metadata OID.

    **Requires:** Authentication
    **Security:** User must have access to the image's session
    """
    logger.debug(f"User {user_id} requesting particle by OID: {oid}")

    ppji = db.query(ImageMetaData).filter(ImageMetaData.Oid == oid).all()
    if not ppji:
        raise HTTPException(status_code=404, detail="No Particlepickingjobitem found for Image")

    # ✅ Check session access via the image
    metadata = ppji[0]
    if metadata.image_id:
        db_image = db.query(Image).filter(Image.oid == metadata.image_id).first()
        if db_image and db_image.session_id:
            if not check_session_access(user_id, db_image.session_id, action="read"):
                logger.warning(f"SECURITY: User {user_id} denied particle access for OID: {oid}")
                raise HTTPException(status_code=403, detail="Access denied to this particle data")

    return metadata.data


@particles_router.put("/particle-pickings", summary="Update particle picking data")
async def update_particle_picking(
    body_req: ParticlePickingDto,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Update particle picking data.

    **Requires:** Authentication
    **Security:** User must have write access to the image's session
    """
    logger.info(f"User {user_id} updating particle picking: {body_req.oid}")

    try:
        image_meta_data = db_session.query(ImageMetaData).filter(ImageMetaData.oid == body_req.oid).first()
        if not image_meta_data:
            raise HTTPException(status_code=404, detail="Particle picking  not found")

        # ✅ Check session access via the image
        if image_meta_data.image_id:
            db_image = db_session.query(Image).filter(Image.oid == image_meta_data.image_id).first()
            if db_image and db_image.session_id:
                if not check_session_access(user_id, db_image.session_id, action="write"):
                    logger.warning(f"SECURITY: User {user_id} denied particle picking update for OID: {body_req.oid}")
                    raise HTTPException(status_code=403, detail="Access denied to update this particle data")

        if body_req.data:
            image_meta_data.data_json = json.loads(body_req.data)

        # db_session.merge(body_req)
        db_session.commit()
        db_session.refresh(image_meta_data)
        logger.info(f"User {user_id} successfully updated particle picking: {body_req.oid}")
    except Exception as e:
        db_session.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating Particle picking : {str(e)}")
    return image_meta_data
