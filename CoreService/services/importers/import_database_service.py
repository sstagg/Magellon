from datetime import datetime
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from models.sqlalchemy_models import Project, Msession, ImageJob, Image
from models.pydantic_models import ImportJobBase

class ImportDatabaseService:
    """Service class for handling all database operations related to imports"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def initialize_import_records(self, params: ImportJobBase) -> tuple[Optional[Project], Optional[Msession], ImageJob]:
        """Initialize all necessary database records for an import job"""
        project = None
        if params.magellon_project_name:
            project = self.get_or_create_project(params.magellon_project_name)

        msession = None
        if params.magellon_session_name or params.session_name:
            msession = self.get_or_create_session(
                params.magellon_session_name or params.session_name,
                project.oid if project else None
            )

        job = self.create_job_record(params.session_name, msession.oid if msession else None)
        
        return project, msession, job

    def get_or_create_project(self, project_name: str) -> Project:
        """Get existing project or create new one"""
        project = self.db_session.query(Project).filter(
            Project.name == project_name
        ).first()

        if not project:
            project = Project(
                oid=uuid.uuid4(),
                name=project_name,
                created_date=datetime.now()
            )
            self.db_session.add(project)
            self.db_session.commit()
            self.db_session.refresh(project)

        return project

    def get_or_create_session(self, session_name: str, project_id: Optional[uuid.UUID]) -> Msession:
        """Get existing session or create new one"""
        session = self.db_session.query(Msession).filter(
            Msession.name == session_name
        ).first()

        if not session:
            session = Msession(
                oid=uuid.uuid4(),
                name=session_name,
                project_id=project_id,
                created_date=datetime.now()
            )
            self.db_session.add(session)
            self.db_session.commit()
            self.db_session.refresh(session)

        return session

    def create_job_record(self, session_name: str, msession_id: Optional[uuid.UUID]) -> ImageJob:
        """Create the main job record"""
        job = ImageJob(
            oid=uuid.uuid4(),
            name=f"Import: {session_name}",
            description=f"Import job for session: {session_name}",
            created_date=datetime.now(),
            msession_id=msession_id,
            status_id=1
        )
        self.db_session.add(job)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def create_image_record(self, image_data: dict, session_id: Optional[uuid.UUID] = None) -> Image:
        """Create an Image record from provided data"""
        properties = {
            "oid": uuid.uuid4(),
            "created_date": datetime.now(),
            "session_id": session_id
        }

        # Map all existing properties
        field_mapping = {
            "name", "path", "magnification", "defocus", "dose", "pixel_size",
            "binning_x", "binning_y", "stage_x", "stage_y", "stage_alpha_tilt",
            "atlas_dimxy", "atlas_delta_row", "atlas_delta_column", "level",
            "previous_id", "acceleration_voltage", "spherical_aberration",
            "parent_id", "dimension_x", "dimension_y", "exposure_time",
            "frame_count"
        }

        properties.update({
            field: image_data[field]
            for field in field_mapping
            if field in image_data
        })

        image = Image(**properties)
        self.db_session.add(image)
        self.db_session.commit()
        self.db_session.refresh(image)
        return image
