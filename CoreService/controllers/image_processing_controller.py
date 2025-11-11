import logging
import os
import shutil
import tempfile
import uuid
from typing import Dict
from uuid import UUID

import mrcfile
import numpy as np
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from pydantic import BaseModel
from starlette.responses import FileResponse
from typing import Optional

from config import MAGELLON_HOME_DIR
from controllers.image_processing_tools import lowpass_filter
from models.pydantic_models import LeginonFrameTransferJobBase, LeginonFrameTransferJobDto, \
    EpuImportJobBase, EpuImportJobDto
from services.importers.EPUImporter import EPUImporter
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService
from sqlalchemy.orm import Session
from database import get_db
# from services.image_fft_service import ImageFFTService
from services.mrc_image_service import MrcImageService
from dependencies.auth import get_current_user_id
from dependencies.permissions import require_permission

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
async def png_of_mrc_dir(
    in_dir: str,
    out_dir: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Convert directory of MRC files to PNG images.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    **Warning:** Direct file path access - ensure paths are validated
    """
    logger.warning(f"User {user_id} converting MRC directory to PNG: in_dir={in_dir}, out_dir={out_dir}")
    try:
        mrc_service.convert_mrc_dir_to_png(in_dir=in_dir, out_dir=out_dir)
        logger.info(f"User {user_id} successfully converted MRC directory to PNG")
        return {"message": "MRC files successfully converted to PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to convert MRC directory: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


@image_processing_router.post("/png_of_mrc_file",
                              summary="gets a mrc file, converts it to a PNG image, and saves the resulting image to "
                                      "the output directory (if provided). If the out_dir argument is not specified, "
                                      "the PNG files are saved in the same directory as the MRC files. ")
async def png_of_mrc_file(
    abs_file_path: str,
    out_dir: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Convert single MRC file to PNG image.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.info(f"User {user_id} converting MRC file to PNG: {abs_file_path}")
    try:
        mrc_service.convert_mrc_to_png(abs_file_path=abs_file_path, out_dir=out_dir)
        logger.info(f"User {user_id} successfully converted MRC file to PNG")
        return {"message": "MRC file successfully converted to PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to convert MRC file: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


@image_processing_router.post("/fft_of_mrc_dir",
                              summary="Reads each MRC file from the input directory, converts it to a fft PNG image, "
                                      "and saves the resulting image to the output directory (if provided). If the "
                                      "out_dir argument is not specified, the PNG files are saved in the same "
                                      "directory as the MRC files. ")
async def fft_of_mrc_dir(
    in_dir: str,
    out_dir: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Generate FFT for directory of MRC files.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.warning(f"User {user_id} computing FFT for MRC directory: in_dir={in_dir}, out_dir={out_dir}")
    try:
        mrc_service.compute_dir_fft(in_dir=in_dir, out_dir=out_dir)
        logger.info(f"User {user_id} successfully computed FFT for MRC directory")
        return {"message": "MRC files successfully converted to FFT PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to compute FFT for directory: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


@image_processing_router.post("/fft_of_mrc_file",
                              summary="gets a mrc file, converts it to a fft PNG image, and saves the resulting image "
                                      "to the output directory (if provided). If the out_dir argument is not "
                                      "specified, the PNG files are saved in the same directory as the MRC files. ")
async def fft_of_mrc_file(
    abs_file_path: str,
    abs_out_file_name: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Generate FFT for single MRC file.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.info(f"User {user_id} computing FFT for MRC file: {abs_file_path}")
    try:
        mrc_service.compute_mrc_fft(mrc_abs_path=abs_file_path, abs_out_file_name=abs_out_file_name)
        logger.info(f"User {user_id} successfully computed FFT for MRC file")
        return {"message": "MRC file successfully converted to fft PNG!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to compute FFT: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


@image_processing_router.post("/ctf")
async def calculate_ctf(
    abs_file_path: str,
    abs_out_file_name: str = "",
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Calculate the CTF of an image.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions
    """
    logger.info(f"User {user_id} calculating CTF for file: {abs_file_path}")
    try:
        mrc_service.calculate_and_save_ctf(mrc_path=abs_file_path, save_path=abs_out_file_name)
        logger.info(f"User {user_id} successfully calculated CTF")
        return {"message": "CTF calculated successfully!", "processed_by": str(user_id)}
    except Exception as e:
        logger.error(f"User {user_id} failed to calculate CTF: {str(e)}")
        return {"error": str(e), "user_id": str(user_id)}


# @image_processing_router.post("/epu_images_job")
# def process_epu_import(input_data: EPUFrameTransferJobBase, db: Session = Depends(get_db)):
#     epu_frame_transfer_process(input_data, db)


class LeginonImportResponse(BaseModel):
    status: str
    message: str
    job_id: uuid.UUID = None


@image_processing_router.post("/import_leginon_job")
def process_image_job(
    magellon_project_name: str = Form(...),
    magellon_session_name: str = Form(...),
    camera_directory: str = Form(...),
    session_name: str = Form(...),
    copy_images: bool = Form(False),
    retries: int = Form(0),

    leginon_mysql_host: Optional[str] = Form(None),
    leginon_mysql_port: Optional[int] = Form(None),
    leginon_mysql_db: Optional[str] = Form(None),
    leginon_mysql_user: Optional[str] = Form(None),
    leginon_mysql_pass: Optional[str] = Form(None),

    replace_type: str = Form("none"),
    replace_pattern: Optional[str] = Form(None),
    replace_with: Optional[str] = Form(None),

    defects_file: Optional[UploadFile] = File(None),
    gains_file: Optional[UploadFile] = File(None),

    db: Session = Depends(get_db),
    _: None = Depends(require_permission('msession', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Import data from Leginon system.

    **Requires:** 'create' permission on 'msession' resource
    **Security:** Creates new sessions/images, requires creation permission
    """

    # ✅ Create your Pydantic model manually
    input_data = LeginonFrameTransferJobBase(
        magellon_project_name=magellon_project_name,
        magellon_session_name=magellon_session_name,
        camera_directory=camera_directory,
        session_name=session_name,
        copy_images=copy_images,
        retries=retries,
        leginon_mysql_host=leginon_mysql_host,
        leginon_mysql_port=leginon_mysql_port,
        leginon_mysql_db=leginon_mysql_db,
        leginon_mysql_user=leginon_mysql_user,
        leginon_mysql_pass=leginon_mysql_pass,
        replace_type=replace_type,
        replace_pattern=replace_pattern,
        replace_with=replace_with,
    )

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
        defects_file=defects_file,
        gains_file=gains_file,
        task_list=[],
    )


    logger.warning(f"User {user_id} importing Leginon job: session={magellon_session_name}")

    lft_service.setup_data(job_dto)
    result = lft_service.process(db)

    logger.info(f"User {user_id} completed Leginon import: job_id={job_id}")
    return {**result, "imported_by": str(user_id)}




@image_processing_router.post("/import_epu_job")
def import_epu_job(
    input_data: EpuImportJobBase,
    db: Session = Depends(get_db),
    _: None = Depends(require_permission('msession', 'create')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
):
    """
    Import data from EPU system.

    **Requires:** 'create' permission on 'msession' resource
    **Security:** Creates new sessions/images, requires creation permission
    """
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

    logger.warning(f"User {user_id} importing EPU job: session={input_data.magellon_session_name}")

    job_dto.target_directory = os.path.join(MAGELLON_HOME_DIR, job_dto.session_name)
    epu_importer = EPUImporter()
    epu_importer.setup_data(job_dto)
    result = epu_importer.process(db)

    logger.info(f"User {user_id} completed EPU import: job_id={job_id}")
    return {**result, "imported_by": str(user_id)}


def do_low_pass_filter(file_path: str, output_path: str, p_resolution:float) -> Dict:
    """
    Process MRC file with Gaussian low-pass filtering.

    Args:
        file_path: Path to the input MRC file
        output_path: Path where the processed MRC file will be saved
        p_resolution: Target resolution in angstroms

    Returns:
        Dict with processing results including status and file paths
    """

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found: {file_path}")

    logger.info(f"Processing {file_path}")
    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    try:
        with mrcfile.open(file_path, permissive=True) as mrc:
            image = np.array(mrc.data, copy=True)
            voxel_size = mrc.voxel_size  # Preserve header information
            pixel_size = voxel_size['x']  # assuming uniform pixel size
            logger.debug(f"Pixel size: {pixel_size}Å, Image dtype: {image.dtype}")

            # Get header information to preserve
            nx = mrc.header.nx
            ny = mrc.header.ny
            nz = mrc.header.nz

        # Apply low-pass filter
        filtered = lowpass_filter(image, p_resolution, pixel_size)

        # Save processed image
        with mrcfile.new(output_path, overwrite=True) as mrc_processed:
            mrc_processed.set_data(filtered)
            mrc_processed.voxel_size = voxel_size
            mrc_processed.header.nx = nx
            mrc_processed.header.ny = ny
            mrc_processed.header.nz = nz

        return {
            "status": "success",
            "input_file": file_path,
            "output_file": output_path,
            "resolution": p_resolution,
            "pixel_size": float(pixel_size)
        }

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")



@image_processing_router.post("/low-pass-from-path/", summary="Process an MRC file using file paths")
async def do_low_pass_from_path(
    input_path: str,
    output_path: str,
    p_resolution: float,
    _: None = Depends(require_permission('image_processing', 'write')),  # ✅ Permission check
    user_id: UUID = Depends(get_current_user_id)  # ✅ Audit trail
) -> Dict:
    """
    Process an MRC file with Gaussian low-pass filtering.

    **Requires:** 'write' permission on 'image_processing' resource
    **Security:** User must have image processing permissions

    Args:
        input_path: Path to the input MRC file
        output_path: Path where the processed MRC file will be saved
        p_resolution: Target resolution in angstroms

    Returns:
        Dict: Processing results including status and file paths
    """
    logger.info(f"User {user_id} applying low-pass filter: input={input_path}, resolution={p_resolution}")
    try:
        result = do_low_pass_filter(input_path, output_path, p_resolution)
        logger.info(f"User {user_id} successfully applied low-pass filter")
        return {**result, "processed_by": str(user_id)}
    except FileNotFoundError as e:
        logger.error(f"User {user_id} - File not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"User {user_id} - Error in low-pass filter: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@image_processing_router.post("/low-pass-from-upload/", summary="Process an uploaded MRC file")
async def do_low_pass_from_upload(
    p_resolution: float,
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Process an uploaded MRC file and return the processed file for download.

    **Requires:** Authentication (all authenticated users can upload and process)
    **Security:** User uploads their own file - no database access required

    Args:
        p_resolution: Target resolution in angstroms
        file: Uploaded MRC file

    Returns:
        FileResponse: The processed MRC file
    """
    logger.info(f"User {user_id} uploading file for low-pass filter: {file.filename}, resolution={p_resolution}")
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
        result = do_low_pass_filter(temp_input_path, temp_output_path, p_resolution)
        logger.info(f"User {user_id} processed uploaded file: {result}")

        # Clean up the input temp file
        os.unlink(temp_input_path)

        # Return the processed file
        logger.info(f"User {user_id} returning processed file: processed_{os.path.basename(file.filename)}")
        return FileResponse(
            temp_output_path,
            media_type="application/octet-stream",
            filename=f"processed_{os.path.basename(file.filename)}",
            background=lambda: os.unlink(temp_output_path)  # Clean up after sending file
        )

    except Exception as e:
        # Clean up temp files in case of error
        logger.error(f"User {user_id} - Error processing uploaded file: {str(e)}")
        if 'temp_input_path' in locals() and os.path.exists(temp_input_path):
            os.unlink(temp_input_path)
        if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
            os.unlink(temp_output_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")