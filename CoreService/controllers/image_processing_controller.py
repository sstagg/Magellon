import os
import subprocess
import uuid

from fastapi import APIRouter, HTTPException, Depends

from config import IMAGE_ROOT_DIR
from models.pydantic_models import LeginonFrameTransferJobDto, LeginonFrameTransferJobBase
from models.pydantic_plugins_models import MotionCor2Input
from services.diagrams_service import leginon_frame_transfer_diagram
from services.leginon_frame_transfer_job_service import LeginonFrameTransferJobService
from services.motioncor2_service import build_motioncor2_command
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


# @image_processing_router.post("/ctf")
# async def calculate_ctf(image_file: UploadFile = File(...)):
#     """Calculate the CTF of an uploaded image."""
#     # Load image
#     img = Image.open(BytesIO(await image_file.read())).convert("L")
#     image = np.array(img)
#
#     # Calculate CTF
#     ctf_image = ctf(image)
#
#     # Return CTF as a dictionary
#     return {"ctf": ctf_image.tolist()}


@image_processing_router.post("/motioncor2_cmd")
def run_motioncor2_cmd(input_data: MotionCor2Input):
    # motioncor2_service = MotionCor2Service()
    # motioncor2_service.setup(input_data.json())
    # motioncor2_service.process()
    return {
        "command": build_motioncor2_command(input_data)
    }


@image_processing_router.post("/run_motioncor2")
async def run_motioncor2(input_data: MotionCor2Input):
    # Check if input movie file exists
    # if not os.path.isfile(input_data.input_movie):
    #     raise HTTPException(status_code=400, detail="Input movie file not found.")

    # Create output folder if it doesn't exist
    if not os.path.exists(input_data.output_folder):
        os.makedirs(input_data.output_folder)

    # Run MotionCor2 command
    command = f"MotionCor2 -InMrc {input_data.InMrc} -OutMrc {input_data.output_folder} " \
              f"-Patch 5 5 -Gpu 0 -Bft {input_data.bin}"
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    # Check if MotionCor2 ran successfully
    if process.returncode != 0:
        raise HTTPException(status_code=500, detail=f"MotionCor2 command failed with error: {stderr.decode()}")

    # Return success response with output folder path
    return {"message": "MotionCor2 command successfully executed.",
            "output_folder": input_data.output_folder}


# @image_processing_router.post("/get_png_of_mrc")
# # async def get_png_of_mrc(input: UploadFile = File(...), output: str = ""):
# async def get_png_of_mrc(in_dir: str, out_dir: str = ""):
#     try:
#         # Save the uploaded MRC file to a temporary location
#         input_path = f"/tmp/{in_dir.filename}"
#         with open(input_path, "wb") as buffer:
#             buffer.write(await in_dir.read())
#
#         mrc_service = MrcImageService()
#         # Convert the MRC file to PNG using the MrcService
#         output_path = mrc_service.mrc2png(indir=in_dir, outdir=out_dir)
#         # output_path = mrc_service.mrc2png(input_path, output)
#
#         # Return the converted PNG file
#         with open(output_path, "rb") as buffer:
#             return {"png": buffer.read()}
#     except Exception as e:
#         return {"error": str(e)}

# def process_image_job(source_dir: str, target_dir: str):


#
# {
#     "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
#     "magellon_project_name": "Leginon",
#     "magellon_session_name": "23mar23b",
#     "target_directory": "C:/temp/target",
#     "camera_directory": "/gpfs/research/stagg/framesdata/23mar23b/rawdata",
#     "leginon_mysql_user": "usr_object",
#     "leginon_mysql_pass": "ThPHMn3m39Ds",
#     "leginon_mysql_host": "localhost",
#     "leginon_mysql_port": 3310,
#     "leginon_mysql_db": "dbemdata",
#     "session_name": "23mar23b"
# }

@image_processing_router.get("/diagram")
def generate_diagram():
    return leginon_frame_transfer_diagram()


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
        job_id=job_id,
        target_directory=os.path.join(IMAGE_ROOT_DIR, input_data.magellon_session_name),
        task_list=None  # You can set this to None or any desired value
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
