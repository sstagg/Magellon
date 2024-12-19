import shutil
import uuid
from datetime import datetime
import json
import os
from uuid import UUID
import logging
from typing import List, Optional, Dict, Any

import py7zr
from fastapi import APIRouter, HTTPException, Depends, UploadFile
from sqlalchemy.orm import Session
from config import app_settings
from database import get_db
from models.pydantic_models import ImportJobBase, MagellonImportJobDto
from models.sqlalchemy_models import Msession, Image, ImageMetaData, Project


from services.importers.MagellonImporter import MagellonImporter
from services.importers.import_file_service import ImportFileService

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
            # "metadata": get_image_metadata(db, image.oid),
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
            "images": process_image_hierarchy(db)
        }
        json_path= os.path.join(temp_dir , "session.json")

        save_to_json(result, json_path )
        ImportFileService.copy_directory(from_dir, home_dir)
        #now copy files from home directory to archive
        output_dir = os.path.dirname(temp_dir)  # Go one directory level up
        output_archive = os.path.join(output_dir, session_name + ".mag")
        ImportFileService.create_archive(temp_dir, output_archive,"zip")
        # file_path = ImportFileService.get_archive_path(filename)
        # return FileResponse(file_path, filename=filename)
        return {
            "message": "Archive created successfully",
            "archive": output_archive
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



async def import_session_data(json_data: Dict[Any, Any], db: Session) -> None:
    """Import session data from JSON into database."""
    # First import the msession
    msession_data = json_data["msession"]

    # Convert string UUIDs back to UUID objects
    msession_data["oid"] = uuid.UUID(msession_data["oid"])
    if msession_data["project_id"]:
        msession_data["project_id"] = uuid.UUID(msession_data["project_id"])
    if msession_data["site_id"]:
        msession_data["site_id"] = uuid.UUID(msession_data["site_id"])
    if msession_data["user_id"]:
        msession_data["user_id"] = uuid.UUID(msession_data["user_id"])
    if msession_data["microscope_id"]:
        msession_data["microscope_id"] = uuid.UUID(msession_data["microscope_id"])
    if msession_data["camera_id"]:
        msession_data["camera_id"] = uuid.UUID(msession_data["camera_id"])
    if msession_data["sample_type"]:
        msession_data["sample_type"] = uuid.UUID(msession_data["sample_type"])
    if msession_data["sample_grid_type"]:
        msession_data["sample_grid_type"] = uuid.UUID(msession_data["sample_grid_type"])

    # Convert datetime strings back to datetime objects
    if msession_data["start_on"]:
        msession_data["start_on"] = datetime.fromisoformat(msession_data["start_on"])
    if msession_data["end_on"]:
        msession_data["end_on"] = datetime.fromisoformat(msession_data["end_on"])
    if msession_data["last_accessed_date"]:
        msession_data["last_accessed_date"] = datetime.fromisoformat(msession_data["last_accessed_date"])

    # Create new Msession object
    new_msession = Msession(**msession_data)
    db.add(new_msession)

    # Now process the images hierarchy
    async def process_images(images_data: List[Dict[Any, Any]], parent_id: Optional[uuid.UUID] = None):
        for image_data in images_data:
            # Convert string UUID to UUID object
            image_data["oid"] = uuid.UUID(image_data["oid"])
            image_data["parent_id"] = parent_id

            # Process metadata first so we can reference it
            metadata_list = image_data.pop("metadata", [])
            children = image_data.pop("children", [])

            # Create new Image object
            new_image = Image(**image_data)
            db.add(new_image)

            # Process metadata for this image
            for metadata in metadata_list:
                metadata["oid"] = uuid.UUID(metadata["oid"])
                if metadata["category_id"]:
                    metadata["category_id"] = uuid.UUID(metadata["category_id"])
                if metadata["plugin_id"]:
                    metadata["plugin_id"] = uuid.UUID(metadata["plugin_id"])
                metadata["image_id"] = new_image.oid

                new_metadata = ImageMetaData(**metadata)
                db.add(new_metadata)

            # Process children recursively
            if children:
                await process_images(children, new_image.oid)

    # Start processing the image hierarchy
    await process_images(json_data["images"])

    # Commit all changes
    db.commit()





@export_router.post("/import-dir")
async def import_directory(request: MagellonImportJobDto,  db_session: Session = Depends(get_db)):
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
            raise HTTPException(
                status_code=404,
                detail=f"Source directory not found: {request.source_dir}"
            )

        # Initialize and run importer
        importer = MagellonImporter()
        importer.setup(request)
        result = importer.process(db_session)

        if result.get('status') == 'failure':
            raise HTTPException(
                status_code=500,
                detail=result.get('message', 'Import failed')
            )

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