import os

from models.sqlalchemy_models import Frametransferjob, Frametransferjobitem, Image, Project, Msession, Atlas
from services.file_service import create_directory
from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL,ATLAS_SUB_URL
import logging


logger = logging.getLogger(__name__)

def create_directories(target_dir: str):
    create_directory(target_dir)
    create_directory(os.path.join(target_dir, ORIGINAL_IMAGES_SUB_URL))
    create_directory(os.path.join(target_dir, FRAMES_SUB_URL))
    create_directory(os.path.join(target_dir, FFT_SUB_URL))
    create_directory(os.path.join(target_dir, IMAGE_SUB_URL))
    create_directory(os.path.join(target_dir, THUMBNAILS_SUB_URL))
    create_directory(os.path.join(target_dir, ATLAS_SUB_URL))


def get_information_from_xml_files():
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