import datetime
import os
import time
from typing import Dict, Any
import uuid

from fastapi import HTTPException
from lxml import etree
from io import BytesIO
from typing import List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.helper import custom_replace
from database import get_db
from models.pydantic_models import EPUImportTaskDto
from models.sqlalchemy_models import Image, Msession, Project, ImageJob, ImageJobTask
from fastapi import Depends

from services.importers.BaseImporter import  BaseImporter

import logging
logger = logging.getLogger(__name__)



class EPUMetadata(BaseModel):
    uniqueID: Optional[str] = None
    DoseOnCamera: Optional[float] = None
    Dose: Optional[float] = None
    Defocus: Optional[float] = None
    dimension_x: Optional[int] = None
    binning_x: Optional[int] = None #Field(None, alias="Binning/ns5:x")
    binning_y: Optional[int] = None #Field(None, alias="Binning/ns5:y")
    pixelSize_x: Optional[float] = None
    atlas_delta_row: Optional[float] = None
    atlas_delta_column: Optional[float] = None
    stage_alpha_tilt: Optional[float] = None
    stage_position_x: Optional[float] = None
    stage_position_y: Optional[float] = None

    class Config:
        allow_population_by_field_name = True

namespaces = {
    'ns0': 'http://schemas.datacontract.org/2004/07/Fei.SharedObjects',
    'ns1': 'http://schemas.microsoft.com/2003/10/Serialization/Arrays',
    'ns2': 'http://schemas.datacontract.org/2004/07/Fei.Types',
    'ns3': 'http://schemas.datacontract.org/2004/07/System.Windows.Media',
    'ns4': 'http://schemas.datacontract.org/2004/07/Fei.Common.Types',
    'ns5': 'http://schemas.datacontract.org/2004/07/System.Drawing'
}
def create_image_record(xml_metadata: EPUMetadata, file_path: str, parent_id: Optional[str] = None) -> str:
    """Create and save an Image record from XML metadata"""
    image = Image(
        oid=uuid.uuid4(),
        name=os.path.basename(file_path),
        path=file_path,
        parent_id=parent_id,
        # session_id=session_id,
        dose=xml_metadata.Dose,
        defocus=xml_metadata.Defocus,
        dimension_x=xml_metadata.dimension_x,
        binning_x=xml_metadata.binning_x,
        binning_y=xml_metadata.binning_y,
        pixel_size_x=xml_metadata.pixelSize_x,
        atlas_delta_row=xml_metadata.atlas_delta_row,
        atlas_delta_column=xml_metadata.atlas_delta_column,
        stage_alpha_tilt=xml_metadata.stage_alpha_tilt,
        stage_x=xml_metadata.stage_position_x,
        stage_y=xml_metadata.stage_position_y,
        last_accessed_date=datetime.now(),
        OptimisticLockField=1,
        # Store the full XML metadata in the metadata_ column
        #metadata_=etree.tostring(etree.parse(BytesIO(xml_content)).getroot()).decode('utf-8')
    )

    # db_session.add(image)
    # db_session.flush()  # Flush to get the ID while keeping transaction open
    return str(image.oid)

def parse_xml(xml_content: bytes) -> EPUMetadata:
    root = etree.parse(BytesIO(xml_content))
    metadata = {}

    xpath_mapping = {
        'uniqueID': './/ns0:uniqueID',
        'DoseOnCamera': './/ns0:DoseOnCamera',
        'Dose': './/ns0:Dose',
        'Defocus': './/ns0:Defocus',
        'dimension_x': './/ns0:dimension/ns0:width',
        'binning_x': './/ns0:Binning/ns5:x',
        'binning_y': './/ns0:Binning/ns5:y',
        'pixelSize_x': './/ns0:pixelSize/ns0:x/ns0:numericValue',
        'atlas_delta_row': './/ns0:atlas_delta_row',
        'atlas_delta_column': './/ns0:atlas_delta_column',
        'stage_alpha_tilt': './/ns0:stage_alpha_tilt',
        'stage_position_x': './/ns0:stage/ns0:Position/ns0:X',
        'stage_position_y': './/ns0:stage/ns0:Position/ns0:Y'
    }

    for field, xpath in xpath_mapping.items():
        element = root.find(xpath, namespaces)
        if element is not None:
            value = element.text
            # Convert to appropriate type
            if field in ['dimension_x', 'binning_x', 'binning_y']:
                metadata[field] = int(value) if value else None
            elif 'position' in field or field in ['DoseOnCamera', 'Dose', 'Defocus', 'pixelSize_x', 'atlas_delta_row', 'atlas_delta_column', 'stage_alpha_tilt']:
                metadata[field] = float(value) if value else None
            else:
                metadata[field] = value

    return EPUMetadata(**metadata)

class DirectoryStructure(BaseModel):
    name: str
    type: str
    children: list = None

def scan_directory(path):
    try:
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Path not found")

        if os.path.isfile(path):
            return DirectoryStructure(name=os.path.basename(path), type="file")

        structure = DirectoryStructure(name=os.path.basename(path), type="directory", children=[])

        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            if os.path.isfile(item_path):
                structure.children.append(DirectoryStructure(name=item, type="file"))
            elif os.path.isdir(item_path):
                structure.children.append(scan_directory(item_path))

        return structure
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")






class EPUImporter(BaseImporter):
    def __init__(self):
        super().__init__()
        self.image_tasks = []

    def import_data(self):
        # Implement EPU-specific data import logic
        # This might involve parsing XML files
        pass

    def process_imported_data(self):
        # Implement EPU-specific data processing logic
        pass
    def process(self, db_session: Session = Depends(get_db)) -> Dict[str, str]:
        try:
            start_time = time.time()  # Start measuring the time
            result = self.create_job(db_session)
            end_time = time.time()  # Stop measuring the time

            execution_time = end_time - start_time
            return result

        except Exception as e:
            return {'status': 'failure', 'message': f'Job failed with error: {str(e)} Job ID: {self.params.job_id}'}



    def create_job(self, db_session: Session):
        try:

            magellon_project: Project = None
            magellon_session: Msession = None
            if self.params.magellon_project_name is not None:
                magellon_project = db_session.query(Project).filter(
                    Project.name == self.params.magellon_project_name).first()
                if not magellon_project:
                    magellon_project = Project(name=self.params.magellon_project_name)
                    db_session.add(magellon_project)
                    db_session.commit()
                    db_session.refresh(magellon_project)

            magellon_session_name = self.params.magellon_session_name or self.params.session_name

            if self.params.magellon_session_name is not None:
                magellon_session = db_session.query(Msession).filter(
                    Msession.name == magellon_session_name).first()
                if not magellon_session:
                    magellon_session = Msession(name=magellon_session_name, project_id=magellon_project.oid)
                    db_session.add(magellon_session)
                    db_session.commit()
                    db_session.refresh(magellon_session)

            session_name = self.params.session_name

            epu_image_list=[]
            # NOW Scan the directory and get all xml files and process them and put in epu_image_list


            if len(epu_image_list) > 0:
                    # image_dict = {image["filename"]: image for image in epu_image_list}
                image_dict = {}
                # Create a new job
                job = ImageJob(
                    # Oid=uuid.uuid4(),
                    name="EPU Import: " + session_name,
                    description="EPU Import for session: " +
                                session_name + "in directory: ",
                    created_date=datetime.now(),  #path=session_result["image path"],
                    output_directory=self.params.camera_directory,
                    msession_id=magellon_session.oid
                    # Set other job properties
                )
                db_session.add(job)
                db_session.flush()  # Flush the session to get the generated Oid

                db_image_list = []
                db_job_item_list = []
                separator = "/"
                for image in epu_image_list:
                    filename = image["filename"]
                    # source_image_path = os.path.join(session_result["image path"], filename)

                    db_image = Image(oid=uuid.uuid4(),
                                     name=filename,
                                     magnification=image["mag"],
                                     defocus=image["defocus"],
                                     dose=image["calculated_dose"],
                                     pixel_size=image["pixelsize"],
                                     binning_x=image["bining_x"],
                                     stage_x=image["stage_x"],
                                     stage_y=image["stage_y"],
                                     stage_alpha_tilt=image["stage_alpha_tilt"],
                                     atlas_dimxy=image["dimx"],
                                     atlas_delta_row=image["delta_row"],
                                     atlas_delta_column=image["delta_column"],
                                     binning_y=image["bining_y"],
                                     # level=get_image_levels(filename, presets_result["regex_pattern"]),
                                     previous_id=image["image_id"],
                                     acceleration_voltage=image["acceleration_voltage"],
                                     spherical_aberration=image["spherical_aberration"],
                                     session_id=magellon_session.oid)
                    # get_image_levels(filename,presets_result["regex_pattern"])
                    # db_session.add(db_image)
                    # db_session.flush()
                    db_image_list.append(db_image)
                    image_dict[filename] = db_image.oid
                    # image_dict = {db_image.name: db_image.Oid for db_image in db_image_list}

                    # source_image_path = (session_result["image path"] + separator + filename + ".mrc")
                    # change logic to use image's director instead'
                    source_frame_path = os.path.join(self.params.camera_directory, image["frame_names"])
                    # source_image_path = os.path.join(session_result["image path"], image["image_name"])

                    #TODO:
                    # source_frame_path = source_frame_path.replace("/gpfs/", "Y:/")
                    # source_image_path = source_image_path.replace("/gpfs/", "Y:/")

                    if self.params.replace_type == "regex" or self.params.replace_type == "standard":
                        source_frame_path = custom_replace(source_frame_path, self.params.replace_type,
                                                           self.params.replace_pattern, self.params.replace_with)
                        source_image_path = custom_replace(source_image_path, self.params.replace_type,
                                                           self.params.replace_pattern, self.params.replace_with)

                    # Create a new job item and associate it with the job and image
                    job_item = ImageJobTask(
                        oid=uuid.uuid4(),
                        job_id=job.oid,
                        frame_name=image["frame_names"],
                        frame_path=source_frame_path,
                        image_name=image["image_name"],
                        image_path=source_image_path,
                        status_id=1,
                        stage=0,
                        image_id=db_image.oid,
                        # Set job item properties
                    )
                    db_job_item_list.append(job_item)
                    # db_session.add(job_item)

                    # Get the file name and extension from the source path
                    # source_filename, source_extension = os.path.splitext(source_image_path)

                    task = EPUImportTaskDto(
                        task_id=uuid.uuid4(),
                        task_alias=f"lftj_{filename}_{self.params.job_id}",
                        file_name=f"{filename}",
                        image_id=db_image.oid,
                        image_name=image["image_name"],
                        frame_name=image["frame_names"],
                        image_path=source_image_path,

                        frame_path=source_frame_path,
                        # target_path=self.params.target_directory + "/frames/" + f"{image['frame_names']}{source_extension}",
                        job_dto=self.params,
                        status=1,
                        pixel_size=image["pixelsize"],
                        acceleration_voltage=image["acceleration_voltage"],
                        spherical_aberration=image["spherical_aberration"]
                    )
                    self.params.task_list.append(task)
                    # print(f"Filename: {filename}, Spot Size: {spot_size}")

                # for db_image in db_image_list:
                #     parent_name = get_parent_name(db_image.name)
                #     if parent_name in image_dict:
                #         db_image.parent_id = image_dict[parent_name]

                # update_levels(db_image_list)

                db_session.bulk_save_objects(db_image_list)
                db_session.bulk_save_objects(db_job_item_list)

                db_session.commit()  # Commit the changes

                if self.params.if_do_subtasks if hasattr(self.params, 'if_do_subtasks') else True:
                    self.run_tasks(db_session,magellon_session )


            return {'status': 'success', 'message': 'Job completed successfully.', "job_id": self.params.job_id}
        # self.create_test_tasks()
        except FileNotFoundError as e:
            error_message = f"Source directory not found: {self.params.source_directory}"
            logger.error(error_message, exc_info=True)
            return {"error": error_message, "exception": str(e)}
        except OSError as e:
            error_message = f"Error accessing source directory: {self.params.source_directory}"
            logger.error(error_message, exc_info=True)
            return {"error": error_message, "exception": str(e)}
        except Exception as e:
            error_message = f"An unexpected error occurred: {str(e)}"
            logger.error(error_message, exc_info=True)
            return {"error": error_message, "exception": str(e)}



    def get_image_tasks(self):
        return self.image_tasks

    def parse_epu_xml(self, xml_content: bytes):
        # Use the existing parse_xml function
        # return create_epu_metadata(parse_xml(xml_content))
        return parse_xml(xml_content)