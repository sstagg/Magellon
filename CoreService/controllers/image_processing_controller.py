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
    service.compute_fft(source_path, destination_path)

    # Return a success message as a response
    return {"message": f"FFT computed and saved to {destination_path}"}