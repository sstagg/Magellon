import os
import subprocess
import uuid

from fastapi import APIRouter, HTTPException, Depends

from config import IMAGE_ROOT_DIR
from models.pydantic_models import LeginonFrameTransferJobBase, EPUFrameTransferJobBase
# from models.pydantic_plugins_models import MotionCor2Input
from services.diagrams_service import leginon_frame_transfer_diagram
# from services.epu_frame_transfer_service import epu_frame_transfer_process
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService
# from services.motioncor2_service import build_motioncor2_command
# from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from database import get_db
# from services.image_fft_service import ImageFFTService
from services.mrc_image_service import MrcImageService

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
        mrc_service.compute_file_fft(mrc_abs_path=abs_file_path, abs_out_file_name=abs_out_file_name)
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



@image_processing_router.get("/diagram")
def generate_diagram():
    return leginon_frame_transfer_diagram()


# @image_processing_router.post("/epu_images_job")
# def process_epu_import(input_data: EPUFrameTransferJobBase, db: Session = Depends(get_db)):
#     epu_frame_transfer_process(input_data, db)

@image_processing_router.post("/transfer_images_job")
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
        target_directory=os.path.join(IMAGE_ROOT_DIR, input_data.magellon_session_name),
        task_list=[]  # You can set this to None or any desired value
    )


    # job_dto.job_id = job_id
    job_dto.target_directory = os.path.join(IMAGE_ROOT_DIR, job_dto.session_name)

    # input_json = json.dumps(job_dto.dict(), cls=UUIDEncoder)
    # lft_service.setup(input_json)

    lft_service.setup_data(job_dto)
    lft_service.process(db)

    # Create a client to communicate with the Airflow API
    # airflow_client = Client(None)
    #
    # # Trigger the image processing job in Airflow
    # airflow_client.trigger_dag(
    #     dag_id='image_process_job',
    #     conf={'source_dir': source_dir, 'target_dir': target_dir, 'job_id': job_id.hex}
    # )

    # Return the job ID as the response
    return {"job_id": job_id}

# async def process_image_job(job_request: JobRequest):
#     # Generate a unique job_id
#     job_id = str(uuid.uuid4())
#
#     # Call the Airflow DAG through a web service
#     response = requests.post(
#         "http://localhost:8080/api/experimental/dags/image_process_job/dag_runs",
#         json={
#             "conf": {
#                 "source_dir": job_request.source_dir,
#                 "target_dir": job_request.target_dir,
#                 "job_id": job_id
#             }
#         }
#     )
#
#     # Check the response status
#     if response.status_code != 200:
#         raise HTTPException(
#             status_code=response.status_code,
#             detail="Failed to trigger the image_process_job DAG"
#         )
#
#     return {"job_id": job_id}
