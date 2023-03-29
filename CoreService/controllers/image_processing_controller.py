from fastapi import APIRouter, Depends

from services.image_fft_service import ImageFFTService

image_processing_router = APIRouter()


def get_mrc_service() -> ImageFFTService:
    return ImageFFTService()


@image_processing_router.post("/fft")
async def compute_fft(
        source_path: str,
        destination_path: str,
        service: ImageFFTService = Depends(get_mrc_service)
):
    # Compute the FFT of the MRC file using the service
    # service.compute_fft(source_path, destination_path)
    service.compute_fft("C:\\projects\\Magellon01\\Documentation\\tutorial\\lowpass\\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW.mrc"
                        , "C:\\projects\\Magellon01\\Documentation\\tutorial\\lowpass\\22feb18a_b_00047gr_00036sq_v01_00006hl_00014ex-e-DW-fft.mrc")

    # Return a success message as a response
    return {"message": f"FFT computed and saved to {destination_path}"}