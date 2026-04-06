import os
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.pydantic_models import MagellonImportJobDto, EpuImportJobDto, SerialEMImportJobDto
from models.sqlalchemy_models import ImageJob
from services.job_manager import JobManager, JobStatus
from services.importers.MagellonImporter import MagellonImporter
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_permission

import_router = APIRouter()
logger = logging.getLogger(__name__)


@import_router.get("/validate-magellon-directory")
def validate_directory(
    source_dir: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Validate that a directory contains valid Magellon data structure.

    **Requires:** Authentication
    **Security:** Authenticated users can validate directory structures

    Returns:
    - Dict with validation status and message
    """
    try:
        logger.info(f"User {user_id} validating Magellon directory: {source_dir}")
        # Check source directory exists
        if not os.path.exists(source_dir):
            raise HTTPException(status_code=404, detail="Source directory not found")

        # Check session.json exists
        session_file = os.path.join(source_dir, "session.json")
        if not os.path.exists(session_file):
            raise HTTPException(status_code=400, detail="session.json not found")

        # Check required directories exist
        images_dir = os.path.join(source_dir,"home", "original")
        frames_dir = os.path.join(source_dir,"home", "frames")
        gains_dir = os.path.join(source_dir, "home","frames")

        if not os.path.exists(images_dir):
            raise HTTPException(status_code=400, detail="original directory not found")

        if not os.path.exists(frames_dir):
            raise HTTPException(status_code=400, detail="frames directory not found")

        if not os.path.exists(gains_dir):
            raise HTTPException(status_code=400, detail="gains directory not found")

        logger.debug(f"Directory validation successful for user {user_id}")
        return {"status": "valid", "message": "Directory structure is valid"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating directory for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@import_router.post("/magellon-import")
def import_directory(
    request: MagellonImportJobDto,
    db_session: Session = Depends(get_db),
    _: None = Depends(require_permission('msession', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Import a session from a directory containing session.json and image files.

    **Requires:** 'create' permission on 'msession' resource
    **Security:** Only users with session creation permission can import data

    Directory structure should be:
    /source_directory
        /session.json
        /images/
            image1.mrc
            image2.mrc
            ...
        /frames/
            image1_frames.mrc
            image2_frames.mrc
            ...
    """
    try:
        logger.warning(f"User {user_id} importing Magellon data from: {request.source_dir}")
        # Validate source directory exists
        if not os.path.exists(request.source_dir):
            raise HTTPException( status_code=404, detail=f"Source directory not found: {request.source_dir}"  )

        # Initialize and run importer
        importer = MagellonImporter()
        importer.setup(request, db_session)
        result = importer.process(db_session)

        if result.get('status') == 'failure':
            raise HTTPException(status_code=500, detail=result.get('message', 'Import failed')  )

        logger.info(f"User {user_id} completed Magellon import: {result.get('session_name')}")
        return {
            "message": "Session imported successfully",
            "session_name": result.get('session_name'),
            # "target_directory": request.target_directory,
            "job_id": result.get('job_id'),
            "imported_by": str(user_id)
        }

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"Import failed for user {user_id}: File not found - {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.error(f"Import failed for user {user_id}: Invalid value - {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during import by user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@import_router.get("/job/{job_id}")
def get_job_status(
    job_id: str,
    db_session: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Get the current status of a job by job_id using the JobManager.

    **Requires:** Authentication
    **Security:** Authenticated users can check job status

    Returns:
        dict: Current job status including progress, current task, and completion status
    """
    try:
        logger.debug(f"User {user_id} checking job status: {job_id}")
        # Get job manager instance
        job_manager = JobManager()

        # Get job data
        job_data = job_manager.get_job(job_id)

        if not job_data:
            # Try to get job from database
            job = db_session.query(ImageJob).filter(ImageJob.oid == job_id).first()

            if not job:
                raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

            # Job exists in database but not in job manager
            status_map = {
                1: "pending",
                2: "running",
                3: "running",  # Processing
                4: "completed",
                5: "failed",
                6: "cancelled"
            }

            # Return limited job info from database
            return {
                "job_id": job_id,
                "name": job.name,
                "description": job.description,
                "status": status_map.get(job.status_id, "unknown"),
                "created_at": job.created_date.isoformat() if job.created_date else None,
                "message": "Job exists in database but detailed status is not available"
            }

        # Return job status from job manager
        return job_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving job status for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving job status: {str(e)}"
        )


@import_router.post("/epu-import")
def import_epu_directory(
    request: EpuImportJobDto,
    db_session: Session = Depends(get_db),
    _: None = Depends(require_permission('msession', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Import EPU data from a directory containing XML metadata and image files.

    **Requires:** 'create' permission on 'msession' resource
    **Security:** Only users with session creation permission can import EPU data

    Directory structure should be an EPU session directory containing XML metadata files
    and associated TIFF/EER image files.

    Parameters:
    - request: EPU import job parameters including directory path

    Returns:
    - Dict with import status and session information
    """
    try:
        logger.warning(f"User {user_id} importing EPU data from: {request.epu_dir_path}")
        # Validate source directory exists
        if not os.path.exists(request.epu_dir_path):
            raise HTTPException(
                status_code=404,
                detail=f"EPU directory not found: {request.epu_dir_path}"
            )

        # Initialize and run importer
        from services.importers.EPUImporter import EPUImporter
        importer = EPUImporter()
        importer.setup(request, db_session)
        result = importer.process(db_session)

        if result.get('status') == 'failure':
            raise HTTPException(
                status_code=500,
                detail=result.get('message', 'EPU Import failed')
            )

        logger.info(f"User {user_id} completed EPU import: {result.get('session_name')}")
        return {
            "message": "EPU session imported successfully",
            "session_name": result.get('session_name'),
            "job_id": result.get('job_id'),
            "imported_by": str(user_id)
        }

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"EPU import failed for user {user_id}: File not found - {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.error(f"EPU import failed for user {user_id}: Invalid value - {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during EPU import by user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@import_router.get("/validate-epu-directory")
def validate_epu_directory(
    source_dir: str,
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Validate that a directory contains valid EPU data structure.

    **Requires:** Authentication
    **Security:** Authenticated users can validate directory structures

    Parameters:
    - source_dir: Path to the EPU directory

    Returns:
    - Dict with validation status and message
    """
    try:
        logger.info(f"User {user_id} validating EPU directory: {source_dir}")
        # Check source directory exists
        if not os.path.exists(source_dir):
            raise HTTPException(status_code=404, detail="Source directory not found")

        # Check for XML files
        xml_files = [f for f in os.listdir(source_dir) if f.endswith('.xml')]
        if not xml_files:
            raise HTTPException(status_code=400, detail="No XML metadata files found in directory")

        # Check for image files (TIFF)
        image_files = [f for f in os.listdir(source_dir) if f.endswith('.tiff') or f.endswith('.tif')]
        if not image_files:
            raise HTTPException(status_code=400, detail="No TIFF image files found in directory")

        # Verify matching between XML and image files
        xml_basenames = [os.path.splitext(f)[0] for f in xml_files]
        image_basenames = [os.path.splitext(f)[0] for f in image_files]

        matching_files = set(xml_basenames).intersection(set(image_basenames))
        if not matching_files:
            raise HTTPException(status_code=400, detail="No matching XML and image files found")

        logger.debug(f"EPU directory validation successful for user {user_id}: {len(matching_files)} matching files")
        return {
            "status": "valid",
            "message": f"Directory contains valid EPU data with {len(matching_files)} matching files"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating EPU directory for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@import_router.post("/serialem-import")
def import_serialem_directory(
    request: SerialEMImportJobDto,
    db_session: Session = Depends(get_db),
    _: None = Depends(require_permission('msession', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Import SerialEM data from a directory containing metadata and image files.

    **Requires:** 'create' permission on 'msession' resource
    **Security:** Only users with session creation permission can import SerialEM data

    Directory structure should be a SerialEM session directory containing .mdoc files
    and associated TIFF/EER image files.

    Parameters:
    - request: SerialEM import job parameters including directory path

    Returns:
    - Dict with import status and session information
    """
    try:
        logger.warning(f"User {user_id} importing SerialEM data from: {request.serial_em_dir_path}")
        # Validate source directory exists
        if not os.path.exists(request.serial_em_dir_path):
            raise HTTPException(
                status_code=404,
                detail=f"SerialEM directory not found: {request.serial_em_dir_path}"
            )

        # Initialize and run importer
        from services.importers.SerialEmImporter import SerialEmImporter
        importer = SerialEmImporter()
        importer.setup(request, db_session)
        result = importer.process(db_session)

        if result.get('status') == 'failure':
            raise HTTPException(
                status_code=500,
                detail=result.get('message', 'SerialEM Import failed')
            )

        logger.info(f"User {user_id} completed SerialEM import: {result.get('session_name')}")
        return {
            "message": "SerialEM session imported successfully",
            "session_name": result.get('session_name'),
            "job_id": result.get('job_id'),
            "imported_by": str(user_id)
        }

    except HTTPException:
        raise
    except FileNotFoundError as e:
        logger.error(f"SerialEM import failed for user {user_id}: File not found - {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        logger.error(f"SerialEM import failed for user {user_id}: Invalid value - {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during SerialEM import by user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
