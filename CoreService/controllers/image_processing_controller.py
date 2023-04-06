from fastapi import APIRouter
# from fastapi import APIRouter, Depends, UploadFile, File

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


@image_processing_router.post("/png_of_mrc")
# async def get_png_of_mrc(input: UploadFile = File(...), output: str = ""):
async def get_png_of_mrc(in_dir: str, out_dir: str = ""):
    try:
        mrc_service = MrcImageService()
        # Convert the MRC file to PNG using the MrcService
        mrc_service.mrc2png(indir=in_dir, outdir=out_dir)

    except Exception as e:
        return {"error": str(e)}

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
