import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Dict, Optional

import mrcfile
import numpy as np
import scipy
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from starlette.responses import FileResponse

from config import MAGELLON_HOME_DIR
from models.pydantic_models import LeginonFrameTransferJobBase, EPUFrameTransferJobBase, LeginonFrameTransferJobDto, \
    EpuImportJobBase, EpuImportJobDto
from services.importers.EPUImporter import EPUImporter
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService
from sqlalchemy.orm import Session
from database import get_db
# from services.image_fft_service import ImageFFTService
from services.mrc_image_service import MrcImageService


logger = logging.getLogger(__name__)

image_processing_router = APIRouter()

# def get_mrc_service() -> ImageFFTService:
#     return ImageFFTService()


# @image_processing_router.post("/fft")
# async def compute_fft(
#         source_path: str,
#         destination_path: str,
#         service: ImageFFTService = Depends(get_mrc_service)
# ):
#     # Compute the FFT of the MRC file using the service
#     # service.compute_fft(source_path, destination_path)
#     service.compute_fft(
#         "C:\\projects\\Magellon01\\Documentation\\tutorial\\lowpass\\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW.mrc"
#         ,
#         "C:\\projects\\Magellon01\\Documentation\\tutorial\\lowpass\\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW-fft.mrc")
#
#     # Return a success message as a response
#     return {"message": f"FFT computed and saved to {destination_path}"}

mrc_service = MrcImageService()
lft_service = LeginonFrameTransferJobService()


@image_processing_router.post("/png_of_mrc_dir",
                              summary="Reads each MRC file from the input directory, converts it to a PNG image, "
                                      "and saves the resulting image to the output directory (if provided). If the "
                                      "out_dir argument is not specified, the PNG files are saved in the same "
                                      "directory as the MRC files. ")
async def png_of_mrc_dir(in_dir: str, out_dir: str = ""):
    try:
        # in_dir = "C:/temp/images/"
        # out_dir = "C:/temp/images/"
        mrc_service.convert_mrc_dir_to_png(in_dir=in_dir, out_dir=out_dir)
        return {"message": "MRC files successfully converted to PNG!"}

    except Exception as e:
        return {"error": str(e)}


@image_processing_router.post("/png_of_mrc_file",
                              summary="gets a mrc file, converts it to a PNG image, and saves the resulting image to "
                                      "the output directory (if provided). If the out_dir argument is not specified, "
                                      "the PNG files are saved in the same directory as the MRC files. ")
# async def get_png_of_mrc(input: UploadFile = File(...), output: str = ""):
async def png_of_mrc_file(abs_file_path: str, out_dir: str = ""):
    try:
        # out_dir = "C:/temp/images/"
        mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path, out_dir=out_dir)
        return {"message": "MRC file successfully converted to PNG!"}

    except Exception as e:
        return {"error": str(e)}


@image_processing_router.post("/fft_of_mrc_dir",
                              summary="Reads each MRC file from the input directory, converts it to a fft PNG image, "
                                      "and saves the resulting image to the output directory (if provided). If the "
                                      "out_dir argument is not specified, the PNG files are saved in the same "
                                      "directory as the MRC files. ")
async def fft_of_mrc_dir(in_dir: str, out_dir: str = ""):
    try:
        # in_dir = "C:/temp/images/"
        # out_dir = "C:/temp/images/"
        mrc_service.compute_dir_fft(in_dir=in_dir, out_dir=out_dir)
        return {"message": "MRC files successfully converted to FFT PNG!"}

    except Exception as e:
        return {"error": str(e)}


@image_processing_router.post("/fft_of_mrc_file",
                              summary="gets a mrc file, converts it to a fft PNG image, and saves the resulting image "
                                      "to the output directory (if provided). If the out_dir argument is not "
                                      "specified, the PNG files are saved in the same directory as the MRC files. ")
# async def get_png_of_mrc(input: UploadFile = File(...), output: str = ""):
async def fft_of_mrc_file(abs_file_path: str, abs_out_file_name: str = ""):
    try:
        # out_dir = "C:/temp/images/"
        mrc_service.compute_mrc_fft(mrc_abs_path=abs_file_path, abs_out_file_name=abs_out_file_name)
        return {"message": "MRC file successfully converted to fft PNG!"}

    except Exception as e:
        return {"error": str(e)}


@image_processing_router.post("/ctf")
async def calculate_ctf(abs_file_path: str, abs_out_file_name: str = ""):
    """Calculate the CTF of an uploaded image."""
    try:
        # out_dir = "C:/temp/images/"
        mrc_service.calculate_and_save_ctf(mrc_path=abs_file_path, save_path=abs_out_file_name)
        # Normalize CTF to 0-255 range and convert to uint8
        return {"message": "MRC file successfully converted to fft PNG!"}

    except Exception as e:
        return {"error": str(e)}


# @image_processing_router.post("/epu_images_job")
# def process_epu_import(input_data: EPUFrameTransferJobBase, db: Session = Depends(get_db)):
#     epu_frame_transfer_process(input_data, db)


class LeginonImportResponse(BaseModel):
    status: str
    message: str
    job_id: uuid.UUID = None


@image_processing_router.post("/import_leginon_job")
def process_image_job(input_data: LeginonFrameTransferJobBase, db: Session = Depends(get_db)):
    # Generate a unique job ID

    job_id = uuid.uuid4()
    job_dto = LeginonFrameTransferJobDto(
        magellon_project_name=input_data.magellon_project_name,
        magellon_session_name=input_data.magellon_session_name,
        camera_directory=input_data.camera_directory,
        session_name=input_data.session_name,
        copy_images=input_data.copy_images,
        retries=input_data.retries,
        leginon_mysql_host=input_data.leginon_mysql_host,
        leginon_mysql_port=input_data.leginon_mysql_port,
        leginon_mysql_db=input_data.leginon_mysql_db,
        leginon_mysql_user=input_data.leginon_mysql_user,
        leginon_mysql_pass=input_data.leginon_mysql_pass,

        replace_type=input_data.replace_type,
        replace_pattern=input_data.replace_pattern,
        replace_with=input_data.replace_with,

        job_id=job_id,
        target_directory=os.path.join(MAGELLON_HOME_DIR, input_data.magellon_session_name),
        task_list=[]  # You can set this to None or any desired value
    )


    # job_dto.job_id = job_id
    job_dto.target_directory = os.path.join(MAGELLON_HOME_DIR, job_dto.session_name)

    # input_json = json.dumps(job_dto.dict(), cls=UUIDEncoder)
    # lft_service.setup(input_json)

    lft_service.setup_data(job_dto)
    result= lft_service.process(db)

    # Create a client to communicate with the Airflow API
    # airflow_client = Client(None)
    #
    # # Trigger the image processing job in Airflow
    # airflow_client.trigger_dag(
    #     dag_id='image_process_job',
    #     conf={'source_dir': source_dir, 'target_dir': target_dir, 'job_id': job_id.hex}
    # )

    # Return the job ID as the response
    return result



@image_processing_router.post("/import_epu_job")
def import_epu_job(input_data: EpuImportJobBase, db: Session = Depends(get_db)):
    # Generate a unique job ID

    job_id = uuid.uuid4()
    job_dto = EpuImportJobDto(
        magellon_project_name=input_data.magellon_project_name,
        magellon_session_name=input_data.magellon_session_name,
        camera_directory=input_data.camera_directory,
        session_name=input_data.session_name,
        copy_images=input_data.copy_images,
        retries=input_data.retries,

        epu_dir_path=input_data.epu_dir_path,

        replace_type=input_data.replace_type,
        replace_pattern=input_data.replace_pattern,
        replace_with=input_data.replace_with,

        job_id=job_id,
        target_directory=os.path.join(MAGELLON_HOME_DIR, input_data.magellon_session_name),
        task_list=[]  # You can set this to None or any desired value
    )

    job_dto.target_directory = os.path.join(MAGELLON_HOME_DIR, job_dto.session_name)
    epu_importer = EPUImporter()
    # xml_contents = await file.read()
    # epu_importer.import_data(xml_contents)
    # epu_importer.process_imported_data()
    epu_importer.setup_data(job_dto)
    result= epu_importer.process(db)
    return result


SIG = 7
NSIG = 4
MIN_BLOB_AREA = 400

class FilterParams(BaseModel):
    sigma: float = SIG
    nsigma: float = NSIG
    min_blob_area: int = MIN_BLOB_AREA

def process_individual_images(file_path: str, output_path: str, params: Optional[FilterParams] = None) -> Dict:
    """Process MRC file with Gaussian filtering and blob replacement."""
    if params is None:
        params = FilterParams()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with mrcfile.open(file_path, permissive=True) as mrc:
            image = np.array(mrc.data, copy=True)
            voxel_size = mrc.voxel_size  # Preserve header information
            nx, ny, nz = mrc.header.nx, mrc.header.ny, mrc.header.nz

        # Apply Gaussian filter to the image
        filtered = scipy.ndimage.gaussian_filter(image, sigma=params.sigma)

        # Calculate mean and standard deviation for the filtered image
        mean_value = np.mean(filtered)
        std_deviation = np.std(filtered)
        threshold = mean_value - params.nsigma * std_deviation

        # Create a boolean array where True indicates pixels above the threshold
        boolarray = filtered < threshold

        # Label connected regions (blobs) in the boolean array
        boolarray_int = boolarray.astype(int)
        labeled_array, num_features = scipy.ndimage.label(boolarray_int)

        # Calculate the area (in pixels) of each blob
        blob_areas = np.array([np.sum(labeled_array == j) for j in range(1, num_features + 1)])

        # Replace pixels for blobs with specified areas
        image_mean = np.mean(image)
        features = 0
        for m in range(num_features):
            if params.min_blob_area < blob_areas[m]:
                features += 1
                blob_mask = labeled_array == (m + 1)
                image[blob_mask] = image_mean

        with mrcfile.new(output_path, overwrite=True) as mrc_processed:
            mrc_processed.set_data(image)
            mrc_processed.voxel_size = voxel_size
            mrc_processed.header.nx = nx
            mrc_processed.header.ny = ny
            mrc_processed.header.nz = nz

        return {
            "status": "success",
            "input_file": file_path,
            "output_file": output_path,
            "features_replaced": features,
            "parameters": {
                "sigma": params.sigma,
                "nsigma": params.nsigma,
                "min_blob_area": params.min_blob_area
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")



@@image_processing_router.post("/low-pass-from-path/", summary="Process an MRC file using file paths")
async def process_from_path(input_path: str, output_path: str, params: Optional[FilterParams] = None) -> Dict:
    """
    Process an MRC file with Gaussian filtering and blob replacement.

    Args:
        input_path: Path to the input MRC file
        output_path: Path where the processed MRC file will be saved
        params: Optional processing parameters

    Returns:
        Dict: Processing results including status and number of features replaced
    """
    try:
        result = process_individual_images(input_path, output_path, params)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@image_processing_router.post("/low-pass-from-upload/", summary="Process an uploaded MRC file")
async def process_upload(file: UploadFile = File(...), params: Optional[FilterParams] = None):
    """
    Process an uploaded MRC file and return the processed file for download.

    Args:
        file: Uploaded MRC file
        params: Optional processing parameters

    Returns:
        FileResponse: The processed MRC file
    """
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mrc") as temp_input:
            # Copy uploaded file to temp file
            shutil.copyfileobj(file.file, temp_input)
            temp_input_path = temp_input.name

        # Create output temp file
        temp_output = tempfile.NamedTemporaryFile(delete=False, suffix=".mrc")
        temp_output_path = temp_output.name
        temp_output.close()

        # Process the file
        result = process_individual_images(temp_input_path, temp_output_path, params)

        # Clean up the input temp file
        os.unlink(temp_input_path)

        # Return the processed file
        return FileResponse(
            temp_output_path,
            media_type="application/octet-stream",
            filename=f"processed_{os.path.basename(file.filename)}",
            background=lambda: os.unlink(temp_output_path)  # Clean up after sending file
        )

    except Exception as e:
        # Clean up temp files in case of error
        if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
            os.unlink(temp_output_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")