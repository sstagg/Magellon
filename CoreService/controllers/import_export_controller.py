import asyncio
import shutil
import uuid
from datetime import datetime
import json
import os
from uuid import UUID
import logging
from typing import List, Optional, Dict, Any
from decimal import Decimal, InvalidOperation

import py7zr
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from config import app_settings
from database import get_db
from models.pydantic_models import ImportJobBase, MagellonImportJobDto, EpuImportJobDto, SerialEMImportJobDto
from models.sqlalchemy_models import Msession, Image, ImageMetaData, Project
from sse_starlette.sse import EventSourceResponse
from services.job_manager import JobManager,JobStatus
from services.importers.MagellonImporter import MagellonImporter
from services.importers.import_file_service import ImportFileService

export_router = APIRouter()

logger = logging.getLogger(__name__)


def serialize_datetime(dt: datetime) -> str:
    return dt.isoformat() if dt else None

def serialize_uuid(uuid: UUID) -> str:
    return str(uuid) if uuid else None


def safe_decimal(value):
    if value is None:
        return None
    try:
        # Convert to Decimal while preserving exact representation
        if isinstance(value, Decimal):
            # If it's already a Decimal, normalize it to remove exponents
            return value.normalize()
        # For other types, first convert to string with full precision
        str_val = f"{value:.20f}" if isinstance(value, float) else str(value)
        return Decimal(str_val)
    except InvalidOperation:
        raise ValueError(f"Invalid decimal value: {value}")


    # Helper function for BIGINT and INTEGER values
def safe_bigint(value):
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None

    # Helper function for BIT values
def safe_bit(value):
    return bool(value) if value is not None else None

def get_image_metadata(db: Session, image_id: UUID) -> List[Dict]:
    metadata = db.query(ImageMetaData).filter(
        ImageMetaData.image_id == image_id,
        ImageMetaData.GCRecord.is_(None)
    ).all()

    return [
        {
            "oid": serialize_uuid(md.oid),
            "name": md.name,
            "alias": md.alias,
            "category_id": serialize_uuid(md.category_id),
            "data": md.data,
            "data_json": md.data_json,
            "processed_json": md.processed_json,
            "plugin_id": serialize_uuid(md.plugin_id),
            "status_id": md.status_id,
            "type": md.type
        }
        for md in metadata
    ]



def process_image_hierarchy(db: Session, parent_id: UUID = None, processed_images: set = None, session_id: UUID = None) -> List[Dict]:
    if processed_images is None:
        processed_images = set()

    query = db.query(Image).filter(Image.GCRecord.is_(None))
    if session_id:
        query = query.filter(Image.session_id == session_id)
    if parent_id is not None:
        query = query.filter(Image.parent_id == parent_id)
    else:
        query = query.filter(Image.parent_id.is_(None))

    images = query.all()

    result = []
    for image in images:
        if image.oid in processed_images:
            continue

        processed_images.add(image.oid)
        # Helper function to preserve original value or return None


        image_dict = {
            "oid": serialize_uuid(image.oid),
            "name": image.name,
            "path": image.path,
            "parent_id": serialize_uuid(image.parent_id),
            "session_id": serialize_uuid(image.session_id),

            # BIGINT fields
            "magnification": safe_bigint(image.magnification),
            "spot_size": safe_bigint(image.spot_size),
            "reset_focus": safe_bigint(image.reset_focus),
            "screen_current": safe_bigint(image.screen_current),
            "dimension_x": safe_bigint(image.dimension_x),
            "dimension_y": safe_bigint(image.dimension_y),
            "binning_x": safe_bigint(image.binning_x),
            "binning_y": safe_bigint(image.binning_y),
            "offset_x": safe_bigint(image.offset_x),
            "offset_y": safe_bigint(image.offset_y),
            "exposure_type": safe_bigint(image.exposure_type),
            "previous_id": safe_bigint(image.previous_id),

            # DECIMAL fields
            "dose": safe_decimal(image.dose),
            "focus": safe_decimal(image.focus),
            "defocus": safe_decimal(image.defocus),
            "intensity": safe_decimal(image.intensity),
            "shift_x": safe_decimal(image.shift_x),
            "shift_y": safe_decimal(image.shift_y),
            "beam_shift_x": safe_decimal(image.beam_shift_x),
            "beam_shift_y": safe_decimal(image.beam_shift_y),
            "condenser_x": safe_decimal(image.condenser_x),
            "condenser_y": safe_decimal(image.condenser_y),
            "objective_x": safe_decimal(image.objective_x),
            "objective_y": safe_decimal(image.objective_y),
            "exposure_time": safe_decimal(image.exposure_time),
            "pixel_size_x": safe_decimal(image.pixel_size_x),
            "pixel_size_y": safe_decimal(image.pixel_size_y),

            # Float(asdecimal=True) fields
            "pixel_size": safe_decimal(image.pixel_size),
            "atlas_delta_row": safe_decimal(image.atlas_delta_row),
            "atlas_delta_column": safe_decimal(image.atlas_delta_column),
            "atlas_dimxy": safe_decimal(image.atlas_dimxy),
            "stage_alpha_tilt": safe_decimal(image.stage_alpha_tilt),
            "stage_x": safe_decimal(image.stage_x),
            "stage_y": safe_decimal(image.stage_y),
            "acceleration_voltage": safe_decimal(image.acceleration_voltage),
            "spherical_aberration": safe_decimal(image.spherical_aberration),

            # String fields
            "beam_bank": image.beam_bank,
            "metadata": image.metadata_,
            "frame_name": image.frame_name,

            # BIT field
            "energy_filtered": safe_bit(image.energy_filtered),

            # INTEGER fields
            "OptimisticLockField": safe_bigint(image.OptimisticLockField),
            "GCRecord": safe_bigint(image.GCRecord),
            "level": safe_bigint(image.level),
            "frame_count": safe_bigint(image.frame_count),

            # DateTime field
            "last_accessed_date": image.last_accessed_date.isoformat() if image.last_accessed_date else None,

            # Foreign key
            "atlas_id": serialize_uuid(image.atlas_id),
        }

        children = process_image_hierarchy(db, image.oid, processed_images, session_id)
        if children:
            image_dict["children"] = children

        result.append(image_dict)
    return result


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, Decimal):
            # Convert Decimal to string and handle scientific notation
            s = str(obj)
            if 'E' in s.upper():
                # Split into mantissa and exponent
                mantissa, exp = s.split('E')
                exp = int(exp)
                # Remove decimal point from mantissa and handle negative numbers
                is_negative = mantissa.startswith('-')
                mantissa = mantissa.replace('.', '').replace('-', '')
                # Add decimal point at correct position
                if exp < 0:
                    result = '0.' + '0' * (-exp - 1) + mantissa
                    return '-' + result if is_negative else result
                else:
                    result = mantissa + '0' * exp
                    return '-' + result if is_negative else result
            return s
        return super().default(obj)

def save_to_json(data: Dict, file_path: str) -> str:
    """
    Save the given data to a JSON file with pretty printing, using a custom encoder.

    Args:
        data (Dict): The data to save.
        file_path (str): The path to the JSON file.

    Returns:
        str: The path to the saved JSON file.
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, cls=CustomJSONEncoder, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"Error saving data to JSON: {e}")
    return file_path


def get_project_data(db: Session, project_id: UUID) -> Dict:
    project = db.query(Project).filter(
        Project.oid == project_id,
        Project.GCRecord.is_(None)
    ).first()

    if not project:
        return None

    return {
        "oid": serialize_uuid(project.oid),
        "name": project.name,
        "description": project.description,
        "start_on": serialize_datetime(project.start_on),
        "end_on": serialize_datetime(project.end_on),
        "owner_id": serialize_uuid(project.owner_id),
        "last_accessed_date": serialize_datetime(project.last_accessed_date)
    }

@export_router.post("/export")
async def create_archive(session_name: str, db: Session = Depends(get_db)):
    """
    Endpoint to create an archive from given paths.

    Returns:
        dict: Information about created archive
    """
    try:
        msession = db.query(Msession).filter(            Msession.name == session_name, Msession.GCRecord.is_(None)  ).first()
        if not msession:
            raise HTTPException(status_code=404, detail="Session not found")
        # Get project data if available
        project_data = None
        if msession.project_id:
            project_data = get_project_data(db, msession.project_id)
        from_dir=os.path.join(app_settings.directory_settings.MAGELLON_HOME_DIR, session_name)
        if not os.path.exists(from_dir):
            raise HTTPException(status_code=404, detail="Home directory is empty")
            return

        # Add metadata to the export
        metadata = {
            "exporter": "Magellon Essential Data Exporter",
            "version": "1.0",
            "doc_type": "Session Essential Data",
            "export_date": serialize_datetime(datetime.now()),
            "export_format_version": "1.0",
            "created_by": "Magellon Export Service",
            "schema_version": "1.0"
        }
        temp_dir, home_dir = ImportFileService.create_temp_directory(app_settings.directory_settings.MAGELLON_JOBS_DIR)
        # Get root level images (no parent_id)
        result = {
            "metadata": metadata,
            "project": project_data,  # Include project data in export
            "msession": {
                "oid": serialize_uuid(msession.oid),
                "name": msession.name,
                "project_id": serialize_uuid(msession.project_id),
                "site_id": serialize_uuid(msession.site_id),
                "user_id": serialize_uuid(msession.user_id),
                "description": msession.description,
                "start_on": serialize_datetime(msession.start_on),
                "end_on": serialize_datetime(msession.end_on),
                "microscope_id": serialize_uuid(msession.microscope_id),
                "camera_id": serialize_uuid(msession.camera_id),
                "sample_type": serialize_uuid(msession.sample_type),
                "sample_name": msession.sample_name,
                "sample_grid_type": serialize_uuid(msession.sample_grid_type),
                "sample_sequence": msession.sample_sequence,
                "sample_procedure": msession.sample_procedure,
                "last_accessed_date": serialize_datetime(msession.last_accessed_date)
            },
            "images": process_image_hierarchy(db, None, set(), msession.oid)
        }
        json_path= os.path.join(temp_dir , "session.json")

        save_to_json(result, json_path )
        ImportFileService.copy_directory(from_dir, home_dir)
        #now copy files from home directory to archive
        output_dir = os.path.dirname(temp_dir)  # Go one directory level up
        output_archive = os.path.join(output_dir, session_name + ".mag")
        # ImportFileService.create_archive(temp_dir, output_archive,"zip")

        # file_path = ImportFileService.get_archive_path(filename)
        # return FileResponse(file_path, filename=filename)
        return {
            "message": "Archive created successfully",
            "archive": output_archive
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@export_router.get("/validate-magellon-directory")
def validate_directory(source_dir: str):
    try:
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

        return {"status": "valid", "message": "Directory structure is valid"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@export_router.post("/magellon-import")
def import_directory(request: MagellonImportJobDto,  db_session: Session = Depends(get_db)):
    """
    Import a session from a directory containing session.json and image files.

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
        # Validate source directory exists
        if not os.path.exists(request.source_dir):
            raise HTTPException( status_code=404, detail=f"Source directory not found: {request.source_dir}"  )

        # Initialize and run importer
        importer = MagellonImporter()
        importer.setup(request, db_session)
        result = importer.process(db_session)

        if result.get('status') == 'failure':
            raise HTTPException(status_code=500, detail=result.get('message', 'Import failed')  )

        return {
            "message": "Session imported successfully",
            "session_name": result.get('session_name'),
            # "target_directory": request.target_directory,
            "job_id": result.get('job_id')
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during import: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    

    


@export_router.get("/job/{job_id}")
def get_job_status(job_id: str, db_session: Session = Depends(get_db)):
    """
    Get the current status of a job by job_id using the JobManager.

    Returns:
        dict: Current job status including progress, current task, and completion status
    """
    try:
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

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving job status: {str(e)}"
        )

# Enhanced progress streaming endpoint
# class EventSourceResponse(StreamingResponse):
#     def __init__(self, content, **kwargs):
#         media_type = "text/event-stream"
#         headers = kwargs.pop("headers", {})
#         headers.update({
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             "Content-Type": media_type
#         })
#         super().__init__(content=content, media_type=media_type, headers=headers, **kwargs)
#
#
# # Add a new endpoint to stream progress updates
# @export_router.get("/magellon-import-progress/{job_id}")
# async def get_import_progress(job_id: str):
#     """
#     Stream progress updates for an import job using Server-Sent Events.
#     """
#     async def event_generator():
#         while True:
#             if job_id not in import_progress:
#                 yield {"data": json.dumps({"status": "not_found", "message": "Job not found"})}
#                 break
#
#             progress_data = import_progress[job_id]
#             yield {"data": json.dumps(progress_data)}
#
#             # If the job has completed or errored, we can stop streaming
#             if progress_data["status"] in ["completed", "error"]:
#                 # Keep the progress data for a while, then clean up
#                 asyncio.create_task(cleanup_progress(job_id))
#                 break
#
#             await asyncio.sleep(1)  # Update frequency
#
#     return EventSourceResponse(event_generator())
#
# async def cleanup_progress(job_id: str, delay: int = 3600):
#     """Remove progress data after a delay (default: 1 hour)"""
#     await asyncio.sleep(delay)
#     if job_id in import_progress:
#         del import_progress[job_id]



# Add this to the import_export_controller.py file

@export_router.post("/epu-import")
def import_epu_directory(request: EpuImportJobDto, db_session: Session = Depends(get_db)):
    """
    Import EPU data from a directory containing XML metadata and image files.

    Directory structure should be an EPU session directory containing XML metadata files
    and associated TIFF/EER image files.

    Parameters:
    - request: EPU import job parameters including directory path

    Returns:
    - Dict with import status and session information
    """
    try:
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

        return {
            "message": "EPU session imported successfully",
            "session_name": result.get('session_name'),
            "job_id": result.get('job_id')
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during EPU import: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Add this validation endpoint for EPU directories
@export_router.get("/validate-epu-directory")
def validate_epu_directory(source_dir: str):
    """
    Validate that a directory contains valid EPU data structure.

    Parameters:
    - source_dir: Path to the EPU directory

    Returns:
    - Dict with validation status and message
    """
    try:
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

        return {
            "status": "valid",
            "message": f"Directory contains valid EPU data with {len(matching_files)} matching files"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@export_router.post("/serialem-import")
def import_serialem_directory(request: SerialEMImportJobDto, db_session: Session = Depends(get_db)):
    """
    Import SerialEM data from a directory containing metadata and image files.

    Directory structure should be a SerialEM session directory containing .mdoc files
    and associated TIFF/EER image files.

    Parameters:
    - request: SerialEM import job parameters including directory path

    Returns:
    - Dict with import status and session information
    """
    try:
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

        return {
            "message": "SerialEM session imported successfully",
            "session_name": result.get('session_name'),
            "job_id": result.get('job_id')
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error during SerialEM import: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
