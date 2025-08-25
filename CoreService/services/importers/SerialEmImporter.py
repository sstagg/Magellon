import re
import os
import uuid
import time
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import Depends, HTTPException
import shutil
from core.helper import custom_replace, dispatch_ctf_task
from database import get_db
from models.pydantic_models import SerialEMImportTaskDto
from models.sqlalchemy_models import Image, Msession, Project, ImageJob, ImageJobTask
from config import FFT_SUB_URL, GAINS_SUB_URL, IMAGE_SUB_URL, MAGELLON_HOME_DIR, MAGELLON_JOBS_DIR, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, FRAMES_SUFFIX, app_settings, ATLAS_SUB_URL, CTF_SUB_URL

import logging
from services.file_service import copy_file
from services.importers.BaseImporter import BaseImporter, TaskFailedException
from services.mrc_image_service import MrcImageService
import mrcfile
import tifffile
import numpy as np
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger(__name__)

# Model for SerialEM metadata
class SerialEMMetadata(BaseModel):
    oid: Optional[str] = None
    name: Optional[str] = None
    file_path: Optional[str] = None
    magnification: Optional[float] = None
    defocus: Optional[float] = None
    dose: Optional[float] = None
    pixel_size: Optional[float] = None
    binning_x: Optional[int] = None
    binning_y: Optional[int] = None
    stage_alpha_tilt: Optional[float] = None
    stage_x: Optional[float] = None
    stage_y: Optional[float] = None
    acceleration_voltage: Optional[float] = None
    atlas_dimxy: Optional[float] = None
    atlas_delta_row: Optional[float] = None
    atlas_delta_column: Optional[float] = None
    level: Optional[str] = None
    previous_id: Optional[str] = None
    spherical_aberration: Optional[float] = None
    session_id: Optional[str] = None

    class Config:
        allow_population_by_field_name = True

class DirectoryStructure(BaseModel):
    name: str
    path: str
    type: str
    children: list = None

def scan_directory(path):
    try:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Path not found")

        if os.path.isfile(path):
            return DirectoryStructure(name=os.path.basename(path), path=path, type="file")

        structure = DirectoryStructure(name=os.path.basename(path), path=path, type="directory", children=[])

        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                structure.children.append(DirectoryStructure(name=item, path=item_path, type="file"))
            elif os.path.isdir(item_path):
                structure.children.append(scan_directory(item_path))

        return structure
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

def parse_mdoc(file_path: str, settings_file_path: str) -> SerialEMMetadata:
    """Parse a SerialEM .mdoc file and extract metadata"""
    # Define mapping of SerialEM keys to our metadata model
    keys = [
        ('oid', 'oid'),
        ('name', 'name'),
        ('Magnification', 'magnification'),
        ('Defocus', 'defocus'),
        ('ExposureDose', 'dose'),
        ('PixelSpacing', 'pixel_size'),
        ('Binning', 'binning_x'),
        ('Binning', 'binning_y'),
        ('TiltAngle', 'stage_alpha_tilt'),
        ('StagePosition', 'stage_x'),
        ('StagePosition', 'stage_y'),
        ('Voltage', 'acceleration_voltage'),
        ('atlas_dimxy', 'atlas_dimxy'),
        ('atlas_delta_row', 'atlas_delta_row'),
        ('atlas_delta_column', 'atlas_delta_column'),
        ('level', 'level'),
        ('previous_id', 'previous_id'),
        ('spherical_aberration', 'spherical_aberration'),
        ('session_id', 'session_id')
    ]

    result = {new_key: None for _, new_key in keys}

    try:
        with open(file_path, 'r') as file:
            for line in file:
                match = re.match(r"(\w+) = (.+)", line)
                if match:
                    file_key, value = match.groups()

                    # Handle StagePosition as a special case (it has two values)
                    if file_key == "StagePosition":
                        x, y = map(float, value.split())
                        for orig_key, new_key in keys:
                            if orig_key == "StagePosition":
                                if new_key == "stage_x":
                                    result[new_key] = x
                                elif new_key == "stage_y":
                                    result[new_key] = y
                    else:
                        for orig_key, new_key in keys:
                            if orig_key == file_key:
                                try:
                                    result[new_key] = float(value) if '.' in value or value.isdigit() else value
                                except ValueError:
                                    result[new_key] = value
        # Todo get the spherical abbrevation from the settings file
        # it will be like ctffindParams[5]

        
    except Exception as e:
        logger.error(f"Error parsing mdoc file {file_path}: {str(e)}")
    try:
        with open(settings_file_path, 'r') as settings_file:
           for line in settings_file:
            line = line.strip()
            # Check if line starts with CtffindParams
            if line.startswith("CtffindParams"):
                parts = line.split()
                # 5th value has index 5 (0-based)
                result['spherical_aberration'] = float(parts[5])
                break
    except Exception as e:
        logger.error(f"Error reading settings file {settings_file_path}: {str(e)}")

    # Set file path
    result['file_path'] = file_path

    # Set name if not found in the file
    if not result['name']:
        result['name'] = os.path.splitext(os.path.basename(file_path))[0]
    # TOdo convert required strings to float

    return SerialEMMetadata(**result)

def parse_directory(directory_structure,settings_file_path):
    try:
        metadata_list = []

        def traverse_directory(structure):
            if structure.type == "file" and structure.name.endswith(".mdoc"):
                metadata = parse_mdoc(structure.path,settings_file_path)
                metadata_list.append(metadata)
            elif structure.type == "directory" and structure.children:
                for child in structure.children:
                    traverse_directory(child)

        traverse_directory(directory_structure)
        return metadata_list

    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

# def get_frame_file(source_image_path):
#     # Get the base name of the source image without extension
#     base_name = os.path.splitext(source_image_path)[0]

#     # Common frame file extensions
#     frame_extensions = ['.tif','.frames', '.eer', '.tiff']

#     # Check for frame files with common extensions
#     for ext in frame_extensions:
#         frame_path = f"{base_name}{ext}"
#         if os.path.exists(frame_path):
#             return frame_path

#     return None
def convert_tiff_to_mrc(moviename: str, gainname: str, outname: str) -> str:
    """
    Process a movie (TIFF) and gain reference (MRC), then output a summed MRC file.

    Args:
        moviename (str): Path to input TIFF movie.
        gainname (str): Path to input gain MRC file.
        outname (str): Path to output MRC file.

    Returns:
        str: Path to the output file if successful.

    Raises:
        ValueError: If input shapes don’t match or writing fails.
    """
    try:
        # Read movie and convert to float32
        os.makedirs(os.path.dirname(outname), exist_ok=True)
        movie = tifffile.imread(moviename).astype(np.float32)
        gain = mrcfile.read(gainname)
        # Flip gain for alignment (adjust as per your dataset)
        gain = np.fliplr(gain)

        print("Movie dtype/shape:", movie.dtype, movie.shape)
        print("Gain dtype/shape:", gain.dtype, gain.shape)

        if gain.shape != movie.shape[1:]:
            raise ValueError(
                f"Gain shape {gain.shape} must match frame shape {movie.shape[1:]}"
            )

        # Apply gain correction if needed
        # summed = (movie / gain).sum(axis=0)
        summed = movie.sum(axis=0)

        # Write to MRC
        with mrcfile.new(outname, overwrite=True) as m:
            m.set_data(summed.astype(np.float32))

        print("✅ Done! Output written to:", outname)
        return outname

    except Exception as e:
        raise ValueError(f"convertion of tiff to mrc failed- premade image for ctf: {str(e)}") from e
class SerialEmImporter(BaseImporter):
    def __init__(self):
        super().__init__()
        self.image_tasks = []
        self.mrc_service = MrcImageService()

    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        try:
            start_time = time.time()
            result = self.create_db_project_session(db_session)
            end_time = time.time()
            # todo copy gains file
            execution_time = end_time - start_time
            return result

        except Exception as e:
            return {'status': 'failure', 'message': f'Job failed with error: {str(e)}',
                    #  "job_id": str(getattr(self, 'db_job', {}).get('oid', ''))
                     }
    def create_db_project_session(self, db_session: Session):
        try:
            start_time = time.time()
            magellon_project = None
            magellon_session = None

            # Create or find project
            if self.params.magellon_project_name is not None:
                magellon_project = db_session.query(Project).filter(
                    Project.name == self.params.magellon_project_name).first()
                if not magellon_project:
                    magellon_project = Project(name=self.params.magellon_project_name)
                    db_session.add(magellon_project)
                    db_session.commit()
                    db_session.refresh(magellon_project)

            magellon_session_name = self.params.magellon_session_name or self.params.session_name

            # Create or find session
            if self.params.magellon_session_name is not None:
                magellon_session = db_session.query(Msession).filter(
                    Msession.name == magellon_session_name).first()
                if not magellon_session:
                    magellon_session = Msession(
                        name=magellon_session_name,
                        project_id=magellon_project.oid
                    )
                    db_session.add(magellon_session)
                    db_session.commit()
                    db_session.refresh(magellon_session)

            session_name = self.params.session_name
            settings_dir = os.path.join(self.params.serial_em_dir_path, "settings")
            gains_dir = os.path.join(self.params.serial_em_dir_path, "gains")
            # Scan directory and get all mdoc files
            try:
                files = scan_directory(self.params.serial_em_dir_path)
            except FileNotFoundError as e:
                raise FileNotFoundError(f"SerialEM directory not found: {self.params.serial_em_dir_path}") from e
            if not os.path.isdir(settings_dir):
                raise FileNotFoundError(f"'settings' folder not found in {self.params.serial_em_dir_path}")
            if not os.path.isdir(gains_dir):
                raise FileNotFoundError(f"'gains' folder not found in {self.params.serial_em_dir_path}")
            settings_txt_path = None
            for fname in os.listdir(settings_dir):
                if fname.endswith('.txt'):
                    settings_txt_path = os.path.abspath(os.path.join(settings_dir, fname))
                    break
            if not settings_txt_path:
                raise FileNotFoundError(f"No settings .txt file found in settings directory: {settings_dir}")
            # Find the first file in 'gains' and get its absolute path
            gains_files = [f for f in os.listdir(gains_dir) if os.path.isfile(os.path.join(gains_dir, f))]
            if not gains_files:
                raise FileNotFoundError(f"No files found in gains directory: {gains_dir}")
            gains_file_path = os.path.abspath(os.path.join(gains_dir, gains_files[0]))
            metadata_list = parse_directory(files, settings_txt_path)
            if len(metadata_list) > 0:
                target_dir = os.path.join(MAGELLON_HOME_DIR, self.params.magellon_session_name)
                self.params.target_directory = target_dir
                self.create_directories(self.params.target_directory)

                dest_path = os.path.join(self.params.target_directory, GAINS_SUB_URL)
                gain_file_name = os.path.basename(gains_file_path)

                if not os.path.exists(gains_file_path):
                    raise FileNotFoundError(f"Gains file not found: {gains_file_path}")
                if os.path.isdir(gains_file_path):
                    shutil.copytree(gains_file_path, dest_path, dirs_exist_ok=True)
                else:
                    os.makedirs(dest_path, exist_ok=True)
                    shutil.copy(gains_file_path, dest_path)

                # Create a new job
                job = ImageJob(
                    name=f"SerialEM Import: {session_name}",
                    description=f"SerialEM Import for session: {session_name}",
                    created_date=datetime.now(),
                    output_directory=self.params.camera_directory,
                    msession_id=magellon_session.oid
                )
                db_session.add(job)
                db_session.flush()

                db_image_list = []
                db_job_item_list = []
                task_todo_list = []
                image_dict = {}
                for metadata in metadata_list:
                    metadata.pixel_size *= 1e-10
                    filename = os.path.splitext(os.path.basename(metadata.file_path))[0]
                    db_image = Image(
                        oid=uuid.uuid4(),
                        name=filename,
                        magnification=metadata.magnification,
                        defocus=metadata.defocus,
                        dose=metadata.dose,
                        pixel_size=metadata.pixel_size,
                        binning_x=metadata.binning_x,
                        binning_y=metadata.binning_y,
                        stage_x=metadata.stage_x,
                        stage_y=metadata.stage_y,
                        stage_alpha_tilt=metadata.stage_alpha_tilt,
                        atlas_delta_row=metadata.atlas_delta_row,
                        atlas_delta_column=metadata.atlas_delta_column,
                        acceleration_voltage=metadata.acceleration_voltage,
                        spherical_aberration=metadata.spherical_aberration,
                        session_id=magellon_session.oid
                    )

                    db_image_list.append(db_image)
                    image_dict[filename] = db_image.oid
                    task_id = uuid.uuid4()

                    directory_path = os.path.join(
                        os.environ.get("MAGELLON_JOBS_PATH", "/jobs"),
                        str(task_id)
                    )

                    try:
                        result_file = convert_tiff_to_mrc(
                            metadata.file_path.replace(".mdoc", ""),
                            os.path.join(self.params.target_directory, GAINS_SUB_URL, gain_file_name),
                            os.path.join(directory_path, f"{'.'.join(os.path.basename(metadata.file_path).split('.')[:-2])}.mrc")
                        )
                    except ValueError as err:
                        logger.error(f"Convertion of TIFF to MRC preview image failed for file {metadata.file_path}: {err}", exc_info=True)
                        raise ValueError(f"Preview image conversion failed for: {metadata.file_path}") from err

                    # Find source image and frame paths
                    source_image_path = result_file
                    source_frame_path = metadata.file_path.replace(".mdoc", "")

                    # Handle path replacements if needed
                    if hasattr(self.params, 'replace_type') and hasattr(self.params, 'replace_pattern') and hasattr(self.params, 'replace_with'):
                        if self.params.replace_type in ["regex", "standard"]:
                            if source_frame_path:
                                source_frame_path = custom_replace(source_frame_path, self.params.replace_type,
                                                                self.params.replace_pattern, self.params.replace_with)
                            source_image_path = custom_replace(source_image_path, self.params.replace_type,
                                                            self.params.replace_pattern, self.params.replace_with)

                    frame_name = os.path.splitext(os.path.basename(source_frame_path))[0] if source_frame_path else ""

                    job_item = ImageJobTask(
                        oid=uuid.uuid4(),
                        job_id=job.oid,
                        frame_name=frame_name,
                        frame_path=source_frame_path,
                        image_name=os.path.splitext(os.path.basename(source_image_path))[0],
                        image_path=source_image_path,
                        status_id=1,
                        stage=0,
                        image_id=db_image.oid,
                    )
                    db_job_item_list.append(job_item)

                    task = SerialEMImportTaskDto(
                        task_id=task_id,
                        task_alias=f"lftj_{filename}_{job.oid}",
                        file_name=f"{filename}",
                        image_id=db_image.oid,
                        image_name=os.path.splitext(os.path.basename(source_image_path))[0],
                        frame_name=frame_name,
                        image_path=source_image_path,
                        frame_path=source_frame_path,
                        job_dto=self.params,
                        status=1,
                        pixel_size=metadata.pixel_size,
                        acceleration_voltage=metadata.acceleration_voltage,
                        spherical_aberration=metadata.spherical_aberration,
                    )
                    task_todo_list.append(task)

                # Save all records
                db_session.bulk_save_objects(db_image_list)
                db_session.bulk_save_objects(db_job_item_list)
                db_session.commit()

                # Run tasks if needed
                if getattr(self.params, 'if_do_subtasks', True):
                    self.run_tasks(task_todo_list)

            execution_time = time.time() - start_time
            logger.info(f"serialEM import completed in {execution_time:.2f} seconds")

            return {'status': 'success', 'message': 'Job completed successfully.', "job_id": job.oid}

        except FileNotFoundError as e:
            error_message = f"File not found error: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': f'EPU import failed: {str(e)}',
                # 'job_id': str(getattr(self, 'db_job', {}).get('oid', ''))
            }
        except OSError as e:
            error_message = f"OS error while accessing files or directories: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': f'EPU import failed: {str(e)}',
                # 'job_id': str(getattr(self, 'db_job', {}).get('oid', ''))
            }
        except ValueError as e:
            error_message = f"Data value error: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': f'EPU import failed: {str(e)}',
                # 'job_id': str(getattr(self, 'db_job', {}).get('oid', ''))
            }
        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            logger.error(error_message, exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': error_message,
                # 'job_id': str(getattr(self, 'db_job', {}).get('oid', ''))
            }

