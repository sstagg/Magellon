import json
import os
import logging
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from config import app_settings
from core.serialization import serialize_datetime, serialize_uuid, safe_decimal, safe_bigint, safe_bit
from database import get_db
from models.sqlalchemy_models import Msession, Image, ImageMetaData, Project
from services.importers.import_file_service import ImportFileService
from dependencies.auth import get_current_user_id
from core.sqlalchemy_row_level_security import check_session_access, get_filtered_db

export_router = APIRouter()
logger = logging.getLogger(__name__)


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
async def create_archive(
    session_name: str,
    db: Session = Depends(get_filtered_db),  # ✅ Auto RLS filtering
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Endpoint to create an archive from given paths.

    **Requires:** Authentication
    **Security:** User can only export sessions they have access to (RLS enforced)

    Returns:
        dict: Information about created archive
    """
    try:
        # Query with automatic RLS filtering - user will only see their accessible sessions
        msession = db.query(Msession).filter(            Msession.name == session_name, Msession.GCRecord.is_(None)  ).first()
        if not msession:
            raise HTTPException(status_code=404, detail="Session not found or access denied")

        # ✅ Explicit session access check for export operation
        if not check_session_access(user_id, msession.oid, "read"):
            logger.warning(f"SECURITY: User {user_id} denied export access to session: {session_name}")
            raise HTTPException(status_code=403, detail="Access denied to export this session")

        logger.warning(f"User {user_id} exporting session: {session_name} (ID: {msession.oid})")
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
        logger.info(f"User {user_id} completed export for session: {session_name}")
        return {
            "message": "Archive created successfully",
            "archive": output_archive,
            "exported_by": str(user_id),
            "session_name": session_name
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during export by user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
