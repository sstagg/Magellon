from datetime import datetime
import json
import os
from uuid import UUID
import logging
from typing import List, Optional, Dict

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from config import app_settings
from database import get_db
from models.sqlalchemy_models import Msession, Image, ImageMetaData

from services.import_export_service import ImportExportService

export_router = APIRouter()

logger = logging.getLogger(__name__)


def serialize_datetime(dt: datetime) -> str:
    return dt.isoformat() if dt else None

def serialize_uuid(uuid: UUID) -> str:
    return str(uuid) if uuid else None


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

def process_image_hierarchy(db: Session, parent_id: UUID = None, processed_images: set = None) -> List[Dict]:
    if processed_images is None:
        processed_images = set()

    images = db.query(Image).filter(
        Image.parent_id == parent_id,
        Image.GCRecord.is_(None)
    ).all()

    result = []
    for image in images:
        if image.oid in processed_images:
            continue

        processed_images.add(image.oid)

        image_dict = {
            "oid": serialize_uuid(image.oid),
            "name": image.name,
            "path": image.path,
            "magnification": image.magnification,
            "dose": float(image.dose) if image.dose else None,
            "focus": float(image.focus) if image.focus else None,
            "defocus": float(image.defocus) if image.defocus else None,
            "pixel_size": float(image.pixel_size) if image.pixel_size else None,
            "dimension_x": image.dimension_x,
            "dimension_y": image.dimension_y,
            "binning_x": image.binning_x,
            "binning_y": image.binning_y,
            "exposure_time": float(image.exposure_time) if image.exposure_time else None,
            "stage_x": float(image.stage_x) if image.stage_x else None,
            "stage_y": float(image.stage_y) if image.stage_y else None,
            "metadata": get_image_metadata(db, image.oid),
            "children": process_image_hierarchy(db, image.oid, processed_images)
        }
        result.append(image_dict)

    return result

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, UUID)):
            return str(obj)
        return super().default(obj)

def save_to_json(data: Dict, file_path: str):
    # Save the data with pretty printing and custom encoder
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, cls=CustomJSONEncoder, ensure_ascii=False)

    return file_path



@export_router.post("/export")
async def create_archive(session_name: str, db: Session = Depends(get_db)):
    """
    Endpoint to create an archive from given paths.

    Returns:
        dict: Information about created archive
    """
    try:
        msession = db.query(Msession).filter(
            Msession.name == session_name,
            Msession.GCRecord.is_(None)
        ).first()
        if not msession:
            raise HTTPException(status_code=404, detail="MSession not found")

        from_dir=os.path.join(app_settings.directory_settings.MAGELLON_HOME_DIR, session_name)
        if not os.path.exists(from_dir):
            raise HTTPException(status_code=404, detail="Home directory is empty")
            return


        temp_dir, home_dir = ImportExportService.create_temp_directory(app_settings.directory_settings.MAGELLON_JOBS_DIR)
        # Get root level images (no parent_id)
        result = {
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
            "images": process_image_hierarchy(db)
        }
        json_path= os.path.join(temp_dir , "session.json")

        save_to_json(result, json_path )
        ImportExportService.copy_directory(from_dir, home_dir)
        #now copy files from home directory to archive
        ImportExportService.create_archive(temp_dir, session_name + ".mag")
        # file_path = ImportExportService.get_archive_path(filename)
        # return FileResponse(file_path, filename=filename)
        # return {
        #     "message": "Archive created successfully",
        #     "archive": os.path.basename(archive_path)
        # }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))