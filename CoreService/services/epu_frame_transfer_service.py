import os

from fastapi import Depends

from database import get_db
from models.pydantic_models import EPUFrameTransferJobBase
from models.sqlalchemy_models import  Image, Project, Msession
from services.file_service import create_directory
from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    ATLAS_SUB_URL
import logging
import uuid
from services.mrc_image_service import MrcImageService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_directories(target_dir: str):
    create_directory(target_dir)
    create_directory(os.path.join(target_dir, ORIGINAL_IMAGES_SUB_URL))
    create_directory(os.path.join(target_dir, FRAMES_SUB_URL))
    create_directory(os.path.join(target_dir, FFT_SUB_URL))
    create_directory(os.path.join(target_dir, IMAGE_SUB_URL))
    create_directory(os.path.join(target_dir, THUMBNAILS_SUB_URL))
    create_directory(os.path.join(target_dir, ATLAS_SUB_URL))


def epu_frame_transfer_process(input_data: EPUFrameTransferJobBase, db_session: Session = Depends(get_db)):
    try:
        magellon_project: Project = None
        magellon_session: Msession = None
        if input_data.magellon_project_name is not None:
            magellon_project = db_session.query(Project).filter(
                Project.name == input_data.magellon_project_name).first()
            if not magellon_project:
                magellon_project = Project(name=input_data.magellon_project_name)
                db_session.add(magellon_project)
                db_session.commit()
                db_session.refresh(magellon_project)

        magellon_session_name = input_data.magellon_session_name or input_data.epu_session_name

        if input_data.magellon_session_name is not None:
            magellon_session = db_session.query(Msession).filter(
                Msession.name == input_data.magellon_session_name).first()
            if not magellon_session:
                magellon_session = Msession(name=input_data.magellon_session_name, project_id=magellon_project.Oid)
                db_session.add(magellon_session)
                db_session.commit()
                db_session.refresh(magellon_session)

        db_image_list = []
        db_image = Image(Oid=uuid.uuid4(), name=filename, magnification=image["mag"],
                         defocus=image["defocus"], dose=image["calculated_dose"],
                         pixel_size=image["pixelsize"], binning_x=image["bining_x"],
                         stage_x=image["stage_x"], stage_y=image["stage_y"],
                         stage_alpha_tilt=image["stage_alpha_tilt"],
                         atlas_dimxy=image["dimx"],
                         atlas_delta_row=image["delta_row"],
                         atlas_delta_column=image["delta_column"],
                         binning_y=image["bining_y"],
                         level=get_image_levels(filename, presets_result["regex_pattern"]),
                         old_id=image["image_id"], session_id=magellon_session.Oid)
        db_session.bulk_save_objects(db_image_list)
        return {'status': 'success', 'message': 'Task completed successfully.'}
    except Exception as e:
        return {'status': 'failure', 'message': f'Task failed with error: {str(e)}'}


