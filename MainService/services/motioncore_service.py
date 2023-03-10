import subprocess
from typing import List

from pydantic import BaseModel, validator


class MotioncoreService:

    def run_motioncor2(self, mrc_files: List[str], dose_per_frame: float, patch_size: int, binning: int) -> bytes:
        # Construct motioncor2 command
        command = ['motioncor2']
        for mrc_file in mrc_files:
            command.append(mrc_file)
        command += [
            '--dose_per_frame', str(dose_per_frame),
            '--patch_size', str(patch_size),
            '--binning', str(binning),
            '--gain_reference', 'Gatan',
            '--bfactor', '100.0',
            '--save_movies',
            '--micrographs_suffix', '_motioncor2.mrc'
        ]

        # Run motioncor2 command
        return subprocess.check_output(command, stderr=subprocess.STDOUT)


class Motioncor2Input(BaseModel):
    mrc_files: List[str]
    dose_per_frame: float
    patch_size: int
    binning: int

    @validator('dose_per_frame')
    def dose_per_frame_positive(cls, v):
        assert v > 0, 'dose_per_frame must be positive'
        return v

    @validator('patch_size')
    def patch_size_multiple_of_two(cls, v):
        assert v % 2 == 0, 'patch_size must be multiple of two'
        return v

    @validator('binning')
    def binning_positive(cls, v):
        assert v > 0, 'binning must be positive'
        return v
