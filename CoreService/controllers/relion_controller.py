import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from models.pydantic_models import ImportJobBase
from models.relion_pydantic_models import RelionStarFileGenerationResponse, RelionSessionValidationResponse, \
    RelionStarFileGenerationRequest
from models.sqlalchemy_models import Msession, Image, ImageMetaData
from services.relion_starfile_service import RelionStarFileService
from dependencies.auth import get_current_user_id
from core.sqlalchemy_row_level_security import check_session_access, get_filtered_db

relion_router = APIRouter()
logger = logging.getLogger(__name__)


@relion_router.post("/generate-relion-starfile", response_model=RelionStarFileGenerationResponse)
def generate_relion_starfile(
        request: RelionStarFileGenerationRequest,
        db: Session = Depends(get_filtered_db),  # ✅ Auto RLS filtering
        user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Generate a RELION star file from database session data.

    **Requires:** Authentication
    **Security:** User can only generate starfiles for sessions they have access to (RLS enforced)

    This endpoint:
    1. Queries the database for session and image data
    2. Applies filters for magnification and movie presence
    3. Extracts CTF parameters from metadata
    4. Creates optics and micrographs data blocks
    5. Generates a RELION-compatible star file
    6. Optionally copies or symlinks MRC files

    Parameters:
    - request: RELION star file generation parameters including filters

    Returns:
    - Dict with generation results and file paths
    """
    try:
        # ✅ First, verify the session exists and user has access
        session = db.query(Msession).filter(
            Msession.name == request.session_name,
            Msession.GCRecord.is_(None)
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found or access denied")

        # ✅ Explicit access check for generation operation
        if not check_session_access(user_id, session.oid, "read"):
            logger.warning(f"SECURITY: User {user_id} denied Relion starfile generation for session: {request.session_name}")
            raise HTTPException(status_code=403, detail="Access denied to generate starfile for this session")

        logger.info(f"User {user_id} generating Relion starfile for session: {request.session_name}")
        service = RelionStarFileService()

        result = service.generate_starfile_from_session(
            session_name=request.session_name,
            output_directory=request.output_directory,
            file_copy_mode=request.file_copy_mode,
            source_mrc_directory=request.source_mrc_directory,
            magnification=request.magnification,
            has_movie=request.has_movie,
            db=db
        )

        logger.info(f"User {user_id} completed Relion starfile generation for session: {request.session_name}")
        # Add user info to result
        result['generated_by'] = str(user_id)
        return RelionStarFileGenerationResponse(**result)

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Relion starfile generation failed for user {user_id}: Invalid value - {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        logger.error(f"Relion starfile generation failed for user {user_id}: File not found - {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating RELION star file for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@relion_router.get("/validate-session-for-starfile/{session_name}", response_model=RelionSessionValidationResponse)
def validate_session_for_starfile(
        session_name: str,
        magnification: Optional[int] = None,
        has_movie: Optional[bool] = None,
        db: Session = Depends(get_filtered_db),  # ✅ Auto RLS filtering
        user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Validate that a session can be used for RELION star file generation.

    **Requires:** Authentication
    **Security:** User can only validate sessions they have access to (RLS enforced)

    Checks:
    - Session exists in database
    - Session contains images matching the specified filters
    - Required parameters are available (pixel size, voltage, etc.)

    Parameters:
    - session_name: Name of the session to validate
    - magnification: Optional magnification filter
    - has_movie: Optional filter for presence of movie frames

    Returns:
    - Dict with validation status and details
    """
    try:
        logger.debug(f"User {user_id} validating session for starfile: {session_name}")
        service = RelionStarFileService()
        result = service.validate_session_for_starfile(session_name, magnification, has_movie, db)

        return RelionSessionValidationResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating session for star file (user {user_id}): {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@relion_router.get("/session/{session_name}/ctf-summary")
def get_session_ctf_summary(
        session_name: str,
        magnification: Optional[int] = None,
        has_movie: Optional[bool] = None,
        db: Session = Depends(get_filtered_db),  # ✅ Auto RLS filtering
        user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get a summary of CTF parameters for a session with optional filtering.

    **Requires:** Authentication
    **Security:** User can only query sessions they have access to (RLS enforced)

    Useful for checking what CTF data is available before generating star files.

    Parameters:
    - session_name: Name of the session
    - magnification: Optional magnification filter
    - has_movie: Optional filter for presence of movie frames

    Returns:
    - Dict with CTF parameter statistics and availability
    """
    try:
        logger.debug(f"User {user_id} requesting CTF summary for session: {session_name}")

        # Get session with RLS filtering - user will only see accessible sessions
        msession = db.query(Msession).filter(
            Msession.name == session_name,
            Msession.GCRecord.is_(None)
        ).first()

        if not msession:
            raise HTTPException(status_code=404, detail=f"Session '{session_name}' not found or access denied")

        # ✅ Explicit access check
        if not check_session_access(user_id, msession.oid, "read"):
            logger.warning(f"SECURITY: User {user_id} denied CTF summary access to session: {session_name}")
            raise HTTPException(status_code=403, detail="Access denied to this session")

        # Build query for images with filters
        query = db.query(Image).filter(
            Image.session_id == msession.oid,
            Image.GCRecord.is_(None),
            Image.path.like('%.mrc')
        )

        # Apply magnification filter if provided
        if magnification is not None:
            query = query.filter(Image.magnification == magnification)

        # Apply movie filter if provided
        if has_movie is not None:
            if has_movie:
                # Filter for images that have movies
                query = query.filter(
                    (Image.frame_count > 1) | (Image.frame_name.isnot(None))
                )
            else:
                # Filter for images that don't have movies
                query = query.filter(
                    (Image.frame_count <= 1) | (Image.frame_count.is_(None)),
                    Image.frame_name.is_(None)
                )

        images = query.all()

        if not images:
            filter_info = {}
            if magnification is not None:
                filter_info['magnification'] = magnification
            if has_movie is not None:
                filter_info['has_movie'] = has_movie

            return {
                "session_name": session_name,
                "total_images": 0,
                "applied_filters": filter_info,
                "message": f"No MRC images found with the specified filters: {filter_info}"
            }

        # Analyze CTF data availability
        ctf_stats = {
            "total_images": len(images),
            "has_defocus": 0,
            "has_pixel_size": 0,
            "has_voltage": 0,
            "has_spherical_aberration": 0,
            "ctf_metadata_count": 0,
            "magnifications": {},
            "has_movie_count": 0,
            "no_movie_count": 0
        }

        for image in images:
            if image.defocus:
                ctf_stats["has_defocus"] += 1
            if image.pixel_size:
                ctf_stats["has_pixel_size"] += 1
            if image.acceleration_voltage:
                ctf_stats["has_voltage"] += 1
            if image.spherical_aberration:
                ctf_stats["has_spherical_aberration"] += 1

            # Track magnifications
            if image.magnification:
                mag_key = str(image.magnification)
                ctf_stats["magnifications"][mag_key] = ctf_stats["magnifications"].get(mag_key, 0) + 1

            # Track movie presence
            if (image.frame_count and image.frame_count > 1) or image.frame_name:
                ctf_stats["has_movie_count"] += 1
            else:
                ctf_stats["no_movie_count"] += 1

            # Count CTF-related metadata
            metadata_count = db.query(ImageMetaData).filter(
                ImageMetaData.image_id == image.oid,
                ImageMetaData.GCRecord.is_(None),
                ImageMetaData.name.ilike('%ctf%')
            ).count()

            if metadata_count > 0:
                ctf_stats["ctf_metadata_count"] += 1

        # Calculate completeness percentages
        total = ctf_stats["total_images"]
        ctf_stats["defocus_completeness"] = (ctf_stats["has_defocus"] / total * 100) if total > 0 else 0
        ctf_stats["pixel_size_completeness"] = (ctf_stats["has_pixel_size"] / total * 100) if total > 0 else 0
        ctf_stats["voltage_completeness"] = (ctf_stats["has_voltage"] / total * 100) if total > 0 else 0
        ctf_stats["spherical_aberration_completeness"] = (ctf_stats["has_spherical_aberration"] / total * 100) if total > 0 else 0
        ctf_stats["ctf_metadata_completeness"] = (ctf_stats["ctf_metadata_count"] / total * 100) if total > 0 else 0

        # Create filter info
        filter_info = {}
        if magnification is not None:
            filter_info['magnification'] = magnification
        if has_movie is not None:
            filter_info['has_movie'] = has_movie

        return {
            "session_name": session_name,
            "session_id": str(msession.oid),
            "applied_filters": filter_info,
            "ctf_statistics": ctf_stats,
            "ready_for_starfile": (
                    ctf_stats["pixel_size_completeness"] > 80 and
                    ctf_stats["voltage_completeness"] > 80
            )
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting CTF summary for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
