import datetime
import glob
import os
import time
from typing import Dict, Any
import uuid

import xml.etree.ElementTree as ET
from fastapi import HTTPException
from lxml import etree
from io import BytesIO
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
import shutil
from core.helper import custom_replace, dispatch_ctf_task
from database import get_db
from models.pydantic_models import EPUImportTaskDto
from models.sqlalchemy_models import Image, Msession, Project, ImageJob, ImageJobTask
from fastapi import Depends

from services.file_service import copy_file
from services.importers.BaseImporter import BaseImporter, TaskFailedException
from config import FFT_SUB_URL, IMAGE_SUB_URL, THUMBNAILS_SUB_URL, ORIGINAL_IMAGES_SUB_URL, FRAMES_SUB_URL, \
    FFT_SUFFIX, FRAMES_SUFFIX, app_settings, ATLAS_SUB_URL, CTF_SUB_URL,MAGELLON_HOME_DIR,GAINS_SUB_URL



import logging

from services.mrc_image_service import MrcImageService

logger = logging.getLogger(__name__)

NAMESPACES = {
    'ns0': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
    'ns1': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
    'ns2': 'http://schemas.datacontract.org/2004/07/Fei.Types',
    'ns3': 'http://schemas.datacontract.org/2004/07/System.Windows.Media',
    'ns4': 'http://schemas.datacontract.org/2004/07/Fei.Common.Types',
    'ns5': 'http://schemas.datacontract.org/2004/07/System.Drawing'
}

class EPUMetadata:
    """Class to hold EPU metadata extracted from XML files"""

    def __init__(self, **kwargs):
        self.oid = kwargs.get('oid')
        self.name = kwargs.get('name')
        self.file_path = kwargs.get('file_path')
        self.magnification = kwargs.get('magnification')
        self.defocus = kwargs.get('defocus')
        self.dose = kwargs.get('dose')
        self.pixel_size = kwargs.get('pixel_size')
        self.binning_x = kwargs.get('binning_x')
        self.binning_y = kwargs.get('binning_y')
        self.stage_alpha_tilt = kwargs.get('stage_alpha_tilt')
        self.stage_x = kwargs.get('stage_x')
        self.stage_y = kwargs.get('stage_y')
        self.acceleration_voltage = kwargs.get('acceleration_voltage')
        self.atlas_dimxy = kwargs.get('atlas_dimxy')
        self.atlas_delta_row = kwargs.get('atlas_delta_row')
        self.atlas_delta_column = kwargs.get('atlas_delta_column')
        self.level = kwargs.get('level')
        self.previous_id = kwargs.get('previous_id')
        self.spherical_aberration = kwargs.get('spherical_aberration')
        self.session_id = kwargs.get('session_id')
        self.frame_name = kwargs.get('frame_name')

        # Optional convenience properties
        self.pixelSize_x = self.pixel_size


class DirectoryStructure:
    """Helper class for directory scanning"""

    def __init__(self, name, path, type, children=None):
        self.name = name
        self.path = path
        self.type = type
        self.children = children or []

# Update EPUMetadata model to match main(3).py keys
# class EPUMetadata(BaseModel):
#     oid: Optional[str] = None
#     name: Optional[str] = None
#     file_path: Optional[str] = None  # We'll keep this from original
#     magnification: Optional[float] = None
#     defocus: Optional[float] = None
#     dose: Optional[float] = None
#     pixel_size: Optional[float] = None
#     binning_x: Optional[int] = None
#     binning_y: Optional[int] = None
#     stage_alpha_tilt: Optional[float] = None
#     stage_x: Optional[float] = None
#     stage_y: Optional[float] = None
#     acceleration_voltage: Optional[float] = None
#     atlas_dimxy: Optional[float] = None
#     atlas_delta_row: Optional[float] = None
#     atlas_delta_column: Optional[float] = None
#     level: Optional[str] = None
#     previous_id: Optional[str] = None
#     spherical_aberration: Optional[float] = None
#     session_id: Optional[str] = None
#
#     class Config:
#         allow_population_by_field_name = True

# Keep the same namespaces

def create_image_record(xml_metadata: EPUMetadata, file_path: str, parent_id: Optional[str] = None) -> str:
    """Create and save an Image record from XML metadata"""
    image = Image(
        oid=uuid.uuid4(),
        name=os.path.basename(file_path),
        path=file_path,
        parent_id=parent_id,
        # session_id=session_id,
        dose=xml_metadata.dose,
        defocus=xml_metadata.defocus,
        # dimension_x=xml_metadata.dimension_x,  # Removed as it's not in main(3).py
        binning_x=xml_metadata.binning_x,
        binning_y=xml_metadata.binning_y,
        pixel_size_x=xml_metadata.pixel_size,
        atlas_delta_row=xml_metadata.atlas_delta_row,
        atlas_delta_column=xml_metadata.atlas_delta_column,
        stage_alpha_tilt=xml_metadata.stage_alpha_tilt,
        stage_x=xml_metadata.stage_x,
        stage_y=xml_metadata.stage_y,
        last_accessed_date=datetime.now(),
        OptimisticLockField=1,
        # Store the full XML metadata in the metadata_ column
        #metadata_=etree.tostring(etree.parse(BytesIO(xml_content)).getroot()).decode('utf-8')
    )

    # db_session.add(image)
    # db_session.flush()  # Flush to get the ID while keeping transaction open
    return str(image.oid)

# Replace parse_xml function with main(3).py version
def parse_xml(file_path: str) -> EPUMetadata:
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Keys from main(3).py
    keys = [
        ('uniqueID', 'oid'),
        ('name', 'name'),
        ('NominalMagnification', 'magnification'),
        ('Defocus', 'defocus'),
        ('Dose', 'dose'),
        ('pixelSize/ns0:x/ns0:numericValue', 'pixel_size'),
        ('Binning/ns5:x', 'binning_x'),
        ('Binning/ns5:y', 'binning_y'),
        ('stage/ns0:Position/ns0:A', 'stage_alpha_tilt'),
        ('stage/ns0:Position/ns0:X', 'stage_x'),
        ('stage/ns0:Position/ns0:Y', 'stage_y'),
        ('AccelerationVoltage', 'acceleration_voltage'),
        ('atlas_dimxy', 'atlas_dimxy'),
        ('atlas_delta_row', 'atlas_delta_row'),
        ('atlas_delta_column', 'atlas_delta_column'),
        ('level', 'level'),
        ('previous_id', 'previous_id'),
        ('spherical_aberration', 'spherical_aberration'),
        ('session_id', 'session_id')
    ]

    # Dictionary to store the results, initialize all values to None
    extracted_data = {key[1]: None for key in keys}

    for key in keys:
        for ns_prefix in namespaces:
            direct_element = root.find(f".//{ns_prefix}:{key[0]}", namespaces)
            if direct_element is not None:
                extracted_data[key[1]] = direct_element.text
                break

        for ns_prefix in namespaces:
            key_value_pairs = root.findall(f".//{ns_prefix}:KeyValueOfstringanyType", namespaces)
            for pair in key_value_pairs:
                key_element = pair.find(f"{ns_prefix}:Key", namespaces)
                value_element = pair.find(f"{ns_prefix}:Value", namespaces)
                if key_element is not None and value_element is not None and key_element.text == key[0]:
                    extracted_data[key[1]] = value_element.text
                    break

    # Convert string values to appropriate types
    if extracted_data['magnification']:
        extracted_data['magnification'] = float(extracted_data['magnification'])
    if extracted_data['defocus']:
        extracted_data['defocus'] = float(extracted_data['defocus'])
    if extracted_data['dose']:
        extracted_data['dose'] = float(extracted_data['dose'])
    if extracted_data['pixel_size']:
        extracted_data['pixel_size'] = float(extracted_data['pixel_size'])
    if extracted_data['binning_x']:
        extracted_data['binning_x'] = int(extracted_data['binning_x'])
    if extracted_data['binning_y']:
        extracted_data['binning_y'] = int(extracted_data['binning_y'])
    if extracted_data['stage_alpha_tilt']:
        extracted_data['stage_alpha_tilt'] = float(extracted_data['stage_alpha_tilt'])
    if extracted_data['stage_x']:
        extracted_data['stage_x'] = float(extracted_data['stage_x'])
    if extracted_data['stage_y']:
        extracted_data['stage_y'] = float(extracted_data['stage_y'])
    if extracted_data['acceleration_voltage']:
        extracted_data['acceleration_voltage'] = float(extracted_data['acceleration_voltage'])
    if extracted_data['atlas_dimxy']:
        extracted_data['atlas_dimxy'] = float(extracted_data['atlas_dimxy'])
    if extracted_data['atlas_delta_row']:
        extracted_data['atlas_delta_row'] = float(extracted_data['atlas_delta_row'])
    if extracted_data['atlas_delta_column']:
        extracted_data['atlas_delta_column'] = float(extracted_data['atlas_delta_column'])
    if extracted_data['spherical_aberration']:
        extracted_data['spherical_aberration'] = float(extracted_data['spherical_aberration'])

    extracted_data['file_path'] = file_path
    return EPUMetadata(**extracted_data)

# class DirectoryStructure(BaseModel):
#     name: str
#     path: str
#     type: str
#     children: list = None



class EPUImporter(BaseImporter):
    """
    Importer class for EPU data from Thermo Fisher Scientific microscopes.

    This class handles importing of EPU session metadata, image records, and processing
    associated files.
    """

    def __init__(self):
        super().__init__()
        self.task_dto_list = []

    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        """
        Main entry point for the EPU import process

        Args:
            db_session: SQLAlchemy database session

        Returns:
            Dict with status information
        """
        try:
            start_time = time.time()

            # Initialize project, session, and job records
            project, session, job = self.initialize_db_records(
                db_session,
                self.params.magellon_project_name,
                self.params.magellon_session_name or self.params.session_name,
                "EPU"
            )
            # Load and process the XML metadata
            epu_metadata_list = self.load_epu_metadata()

            if not epu_metadata_list:
                return {
                    'status': 'failure',
                    'message': 'No EPU metadata found in specified directory'
                }

            # Process the metadata into image and task records
            db_image_list, db_job_task_list, task_dto_list = self.create_image_and_task_records(
                db_session,
                epu_metadata_list,
                job.oid,
                session.oid
            )

            # Save records to database
            db_session.bulk_save_objects(db_image_list)
            db_session.bulk_save_objects(db_job_task_list)
            db_session.commit()

            # Set up target directory for file processing
            target_dir = os.path.join(MAGELLON_HOME_DIR,self.params.magellon_session_name)
            self.params.target_directory=target_dir
            self.create_directories(target_dir)
            source_gains = os.path.join(self.params.epu_dir_path, GAINS_SUB_URL)
            if os.path.exists(source_gains):
                shutil.copytree(source_gains, os.path.join(target_dir, GAINS_SUB_URL), dirs_exist_ok=True)
            else:
                raise Exception("gains folder not found in the root of the input folder")
            # Process file tasks
            if getattr(self.params, 'if_do_subtasks', True):
                self.run_tasks(task_dto_list)

                # Create atlas images if needed
                self.create_atlas_images(db_session, session.oid)

            execution_time = time.time() - start_time
            logger.info(f"EPU import completed in {execution_time:.2f} seconds")

            return {
                'status': 'success',
                'message': 'EPU import completed successfully',
                'job_id': str(job.oid)
            }

        except Exception as e:
            logger.error(f"EPU import failed: {str(e)}", exc_info=True)
            db_session.rollback()
            return {
                'status': 'failure',
                'message': f'EPU import failed: {str(e)}',
                'job_id': str(getattr(self, 'db_job', {}).get('oid', ''))
            }

    def load_epu_metadata(self) -> List[EPUMetadata]:
        """
        Load EPU metadata from XML files in the specified directory

        Returns:
            List of EPUMetadata objects
        """
        if not hasattr(self.params, 'epu_dir_path') or not self.params.epu_dir_path:
            raise ValueError("EPU directory path not specified")

        if not os.path.exists(self.params.epu_dir_path):
            raise FileNotFoundError(f"EPU directory not found: {self.params.epu_dir_path}")

        # Scan directory for XML files
        directory_structure = self.scan_directory(self.params.epu_dir_path)
        return self.parse_directory(directory_structure)

    def scan_directory(self, path: str) -> DirectoryStructure:
        """
        Recursively scan a directory to find XML files

        Args:
            path: Directory path to scan

        Returns:
            DirectoryStructure object representing the directory
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Path not found: {path}")

        if os.path.isfile(path):
            return DirectoryStructure(
                name=os.path.basename(path),
                path=path,
                type="file"
            )

        structure = DirectoryStructure(
            name=os.path.basename(path),
            path=path,
            type="directory"
        )

        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                structure.children.append(DirectoryStructure(
                    name=item,
                    path=item_path,
                    type="file"
                ))
            elif os.path.isdir(item_path):
                structure.children.append(self.scan_directory(item_path))

        return structure

    def parse_directory(self, directory_structure: DirectoryStructure) -> List[EPUMetadata]:
        """
        Find and parse XML files in a directory structure

        Args:
            directory_structure: DirectoryStructure to process

        Returns:
            List of EPUMetadata objects
        """
        metadata_list = []

        def traverse_directory(structure):
            if structure.type == "file" and structure.name.endswith(".xml"):
                try:
                    metadata = self.parse_xml(structure.path)
                    metadata_list.append(metadata)
                except Exception as e:
                    logger.warning(f"Failed to parse XML file {structure.path}: {str(e)}")
            elif structure.type == "directory" and structure.children:
                for child in structure.children:
                    traverse_directory(child)

        traverse_directory(directory_structure)
        return metadata_list

    def parse_xml(self, file_path: str) -> EPUMetadata:
        """
        Parse EPU XML file and extract metadata

        Args:
            file_path: Path to XML file

        Returns:
            EPUMetadata object
        """
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Define metadata fields to extract
        keys = [
            ('uniqueID', 'oid'),
            ('name', 'name'),
            ('NominalMagnification', 'magnification'),
            ('Defocus', 'defocus'),
            ('Dose', 'dose'),
            ('pixelSize/ns0:x/ns0:numericValue', 'pixel_size'),
            ('Binning/ns5:x', 'binning_x'),
            ('Binning/ns5:y', 'binning_y'),
            ('stage/ns0:Position/ns0:A', 'stage_alpha_tilt'),
            ('stage/ns0:Position/ns0:X', 'stage_x'),
            ('stage/ns0:Position/ns0:Y', 'stage_y'),
            ('AccelerationVoltage', 'acceleration_voltage'),
            ('atlas_dimxy', 'atlas_dimxy'),
            ('atlas_delta_row', 'atlas_delta_row'),
            ('atlas_delta_column', 'atlas_delta_column'),
            ('level', 'level'),
            ('previous_id', 'previous_id'),
            ('spherical_aberration', 'spherical_aberration'),
        ]

        # Dictionary to store extracted data
        extracted_data = {key[1]: None for key in keys}

        # Extract values from XML
        for key in keys:
            # Try direct element lookup
            for ns_prefix in NAMESPACES:
                direct_element = root.find(f".//{ns_prefix}:{key[0]}", NAMESPACES)
                if direct_element is not None:
                    extracted_data[key[1]] = direct_element.text
                    break

            # Try key-value pairs
            if extracted_data[key[1]] is None:
                for ns_prefix in NAMESPACES:
                    key_value_pairs = root.findall(f".//{ns_prefix}:KeyValueOfstringanyType", NAMESPACES)
                    for pair in key_value_pairs:
                        key_element = pair.find(f"{ns_prefix}:Key", NAMESPACES)
                        value_element = pair.find(f"{ns_prefix}:Value", NAMESPACES)
                        if (key_element is not None and
                                value_element is not None and
                                key_element.text == key[0]):
                            extracted_data[key[1]] = value_element.text
                            break

        # Convert string values to appropriate types
        self._convert_data_types(extracted_data)

        # Add the file path
        extracted_data['file_path'] = file_path

        return EPUMetadata(**extracted_data)

    def _convert_data_types(self, data: Dict[str, Any]) -> None:
        """
        Convert string values to appropriate types

        Args:
            data: Dictionary of data to convert
        """
        # Numeric fields to convert
        float_fields = [
            'magnification', 'defocus', 'dose', 'pixel_size',
            'stage_alpha_tilt', 'stage_x', 'stage_y',
            'acceleration_voltage', 'atlas_dimxy',
            'atlas_delta_row', 'atlas_delta_column',
            'spherical_aberration'
        ]

        int_fields = ['binning_x', 'binning_y']

        # Convert float fields
        for field in float_fields:
            if data.get(field):
                try:
                    data[field] = float(data[field])
                except (ValueError, TypeError):
                    pass

        # Convert integer fields
        for field in int_fields:
            if data.get(field):
                try:
                    data[field] = int(data[field])
                except (ValueError, TypeError):
                    pass

    def create_image_and_task_records(
            self,
            db_session: Session,
            metadata_list: List[EPUMetadata],
            job_id: uuid.UUID,
            session_id: uuid.UUID
    ) -> tuple[List[Image], List[ImageJobTask], List[EPUImportTaskDto]]:
        """
        Create Image and Task records from EPU metadata

        Args:
            db_session: SQLAlchemy database session
            metadata_list: List of EPUMetadata objects
            job_id: ID of the current job
            session_id: ID of the current session

        Returns:
            Tuple of (db_image_list, db_job_task_list, task_dto_list)
        """
        db_image_list = []
        db_job_task_list = []
        task_dto_list = []

        # Dictionary to map filename to image ID for parent-child relationships
        image_dict = {}
        for metadata in metadata_list:
            # Get filename without extension
            filename = os.path.splitext(os.path.basename(metadata.file_path))[0]

            # Create Image record
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
                session_id=session_id,
                last_accessed_date=datetime.now()
            )

            db_image_list.append(db_image)
            image_dict[filename] = db_image.oid

            # Find image and frame files
            source_image_path = os.path.splitext(metadata.file_path)[0] 
            allowed_exts = ['.tif', '.tiff', '.mrc', '.eer']
            matching_files = [
                f for f in glob.glob(source_image_path + '.*')
                if os.path.splitext(f)[1].lower() in allowed_exts
            ]
            if not matching_files:
                logger.warning(f"No valid image file found for base: {source_image_path}")
            else:
                source_image_path = matching_files[0]
                source_frame_path = self._find_frame_file(source_image_path)
                self.params.session_name=self.params.magellon_session_name
                # Apply path replacements if needed
                if self.params.replace_type in ("regex", "standard"):
                    if source_frame_path:
                        source_frame_path = custom_replace(
                            source_frame_path,
                            self.params.replace_type,
                            self.params.replace_pattern,
                            self.params.replace_with
                        )
                    source_image_path = custom_replace(
                        source_image_path,
                        self.params.replace_type,
                        self.params.replace_pattern,
                        self.params.replace_with
                    )

                # Extract frame name if it exists
                frame_name = ""
                if source_frame_path:
                    frame_name = os.path.splitext(os.path.basename(source_frame_path))[0]

                # Create job task
                job_task = ImageJobTask(
                    oid=uuid.uuid4(),
                    job_id=job_id,
                    frame_name=frame_name,
                    frame_path=source_frame_path,
                    image_name=os.path.splitext(os.path.basename(source_image_path))[0],
                    image_path=source_image_path,
                    status_id=1,
                    stage=0,
                    image_id=db_image.oid,
                )
                db_job_task_list.append(job_task)

                # Create task DTO for file processing
                task_dto = EPUImportTaskDto(
                    task_id=job_task.oid,
                    task_alias=f"epu_{filename}_{job_id}",
                    file_name=filename,
                    image_id=db_image.oid,
                    image_name=os.path.splitext(os.path.basename(source_image_path))[0],
                    frame_name=frame_name,
                    image_path=source_image_path,
                    frame_path=source_frame_path,
                    job_dto=self.params,
                    status=1,
                    pixel_size=( metadata.pixel_size if metadata.pixel_size is not None else self.params.default_data.pixel_size*10**-10),
                    acceleration_voltage = ( metadata.acceleration_voltage / 1000 if metadata.acceleration_voltage is not None else self.params.default_data.acceleration_voltage),
                    spherical_aberration=( metadata.spherical_aberration/ 1000 if metadata.spherical_aberration is not None else self.params.default_data.spherical_aberration)
                )
                task_dto_list.append(task_dto)

        # Set parent-child relationships if needed (not implemented yet)
        # This would identify parent-child relationships based on naming conventions

        return db_image_list, db_job_task_list, task_dto_list

    def _find_frame_file(self, source_image_path: str) -> Optional[str]:
        """
        Find a frame file associated with an image

        Args:
            source_image_path: Path to source image

        Returns:
            Path to frame file or None if not found
        """
        # Get the base name of the source image without extension
        base_name = os.path.splitext(source_image_path)[0]

        # Check for EER file
        eer_file_pattern = f"{base_name}*.eer"
        matching_files = glob.glob(eer_file_pattern)
        if matching_files:
            return matching_files[0]

        # Check for other frame formats
        for ext in ['.frames', '.tif', '.tiff', '.mrc']:
            frame_path = f"{base_name}{ext}"
            if os.path.exists(frame_path):
                return frame_path

        return None

    def run_task(self, task_dto: EPUImportTaskDto) -> Dict[str, str]:
        """
        Process a single EPU task

        Args:
            task_dto: Task data transfer object

        Returns:
            Dict with status and message
        """
        try:
            # Ensure the image path exists and has the correct extension
            base_path = os.path.splitext(task_dto.image_path)[0]
            allowed_exts = ['.tif', '.tiff', '.mrc', '.eer']
            matching_files = [
                f for f in glob.glob(base_path + '.*')
                if os.path.splitext(f)[1].lower() in allowed_exts
            ]

            if not matching_files:
                logger.warning(f"No valid image file found matching: {base_path}.*")
                return {'status': 'failure', 'message': f'Image file not found for base: {base_path}'}

            source_image_path = matching_files[0]
            task_dto.image_path = source_image_path  # Update task DTO

            # 1. Transfer frame if it exists
            if task_dto.frame_path:
                self.transfer_frame(task_dto)

            # 2. Copy original image if specified
            if task_dto.job_dto.copy_images:
                target_image_path = os.path.join(
                    self.get_target_directory(),
                    "original",
                    os.path.basename(source_image_path)
                )
                self.copy_image(task_dto)
                task_dto.image_path = target_image_path  # Update path after copy

            # 3. Convert to PNG
            self.convert_image_to_png(source_image_path)

            # 4. Compute FFT
            self.compute_fft(source_image_path)

            # 5. Compute CTF if needed
            self.compute_ctf(source_image_path, task_dto)

            return {'status': 'success', 'message': 'Task completed successfully.'}

        except Exception as e:
            logger.error(f"Task failed: {str(e)}", exc_info=True)
            raise TaskFailedException(f"Task failed: {str(e)}")

    def _extract_grid_label(self, filename: str) -> str:
        """
        Extract grid label from a filename for EPU data

        Args:
            filename: Image filename

        Returns:
            Grid label string
        """
        # Match pattern like "GridSquare_12345" or extract other relevant identifier
        import re
        # Try to match GridSquare pattern
        match = re.search(r'GridSquare_(\d+)', filename)
        if match:
            return f"gs{match.group(1)}"

        # Default to parent method if no specific pattern found
        return super()._extract_grid_label(filename)