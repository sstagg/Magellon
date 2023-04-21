from typing import Tuple, List, Union

from pydantic import BaseModel


class MotionCor2Input(BaseModel):
    input_movie: str
    output_folder: str
    binning_factor: int
    gpuids: str = '0'  # GPU IDs, default is 0
    nrw: int = 1  # Number of frames in running average window (1, 3, 5, ...). 0 = disabled
    FmRef: int = 0  # Frame to be used as the reference for alignment. Default is the first frame.
    Iter: int = 7  # Maximum iterations for iterative alignment, default is 7
    Tol: float = 0.5  # Tolerance for iterative alignment, in pixels
    Patchrows: int = 0  # Number of patches that divide the y-axis for patch-based alignment. Default 0 corresponds to full frame alignment in that direction.
    Patchcols: int = 0  # Number of patches that divide the x-axis for patch-based alignment. Default 0 corresponds to full frame alignment in that direction.
    MaskCentrow: int = 0  # Y coordinate for the center of the subarea that will be used for alignment. Default 0 corresponds to the center coordinate.
    MaskCentcol: int = 0  # X coordinate for the center of the subarea that will be used for alignment. Default 0 corresponds to the center coordinate.
    MaskSizecols: float = 1.0  # The X size of subarea that will be used for alignment. Default 1.0 corresponds to the full size.
    MaskSizerows: float = 1.0  # The Y size of subarea that will be used for alignment. Default 1.0 corresponds to the full size.
    Bft_global: float = 500.0  # Global B-Factor for alignment. Default is 500.0.
    Bft_local: float = 150.0  # Local B-Factor for alignment. Default is 150.0.
    force_cpu_flat: bool = False  # Use CPU to make frame flat field correction.
    rendered_frame_size: int = 1  # Sum this number of saved frames as a rendered frame in alignment.
    eer_sampling: int = 1  # Upsampling eer frames. Fourier binning will be added to return the results back.
    gainfile: str = ""  # Gain file name.
    forceTiff: bool = False  # Force Tiff will be used to specify motioncor2 input of TIFF file.
    bin: float = 1.0  # Binning factor relative to the dd stack. MotionCor2 takes float value (optional).

    InTiff: str
    OutMrc: str
    FtBin: float = 2.0
    Bft: List[Union[float, int]] = [500, 100]
    Patch: List[int] = [5, 5]
    Group: int = 1
    MaskSize: List[float] = [1.0, 1.0]
    FmDose: float = 0.0
    PixSize: float = 0.0
    kV: float = 0.0
    Dark: str = ""
    Gain: Union[str, List[str]] = ""
    FlipGain: int = 0
    RotGain: int = 0
    Gpu: int = 0
