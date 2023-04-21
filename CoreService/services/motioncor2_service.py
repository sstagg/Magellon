import json
import subprocess
import os
from pathlib import Path

from models.pydantic_plugins_models import MotionCor2Input


# mc2_service = MotionCor2Service(params)
# cmd = mc2_service.build_command()

def build_motioncor2_command(params: MotionCor2Input) -> str:
    cmd = ['motioncor2']
    if params.InTiff is not None:
        cmd.append('-InTiff')
        cmd.append(params.InTiff)
    if params.OutMrc is not None:
        cmd.append('-OutMrc')
        cmd.append(params.OutMrc)
    if params.FtBin is not None:
        cmd.append('-FtBin')
        cmd.append(str(params.FtBin))
    if params.Bft is not None:
        cmd.append('-Bft')
        cmd.append(f'{params.Bft[0]} {params.Bft[1]}')
    if params.Iter is not None:
        cmd.append('-Iter')
        cmd.append(str(params.Iter))
    if params.Tol is not None:
        cmd.append('-Tol')
        cmd.append(str(params.Tol))
    if params.Patch is not None:
        cmd.append('-Patch')
        cmd.append(f'{params.Patch[0]} {params.Patch[1]}')
    if params.Group is not None:
        cmd.append('-Group')
        cmd.append(str(params.Group))
    if params.MaskSize is not None:
        cmd.append('-MaskSize')
        cmd.append(f'{params.MaskSize[0]} {params.MaskSize[1]}')
    if params.FmDose is not None:
        cmd.append('-FmDose')
        cmd.append(str(params.FmDose))
    if params.PixSize is not None:
        cmd.append('-PixSize')
        cmd.append(str(params.PixSize))
    if params.kV is not None:
        cmd.append('-kV')
        cmd.append(str(params.kV))
    if params.Dark is not None:
        cmd.append('-Dark')
        cmd.append(params.Dark)
    if params.Gain is not None:
        for gain_file in params.Gain:
            cmd.append('-Gain')
            cmd.append(gain_file)
    if params.FlipGain is not None:
        cmd.append('-FlipGain')
        cmd.append(str(params.FlipGain))
    if params.RotGain is not None:
        cmd.append('-RotGain')
        cmd.append(str(params.RotGain))
    if params.Gpu is not None:
        cmd.append('-Gpu')
        cmd.append(str(params.Gpu))
    return ' '.join(cmd)


class MotionCor2Service:
    def __init__(self, params: MotionCor2Input):
        self.params = params
        self.log_file = None
        self.output_mrc = None
        self.input_movie = None
        self.output_folder = None
        self.binning_factor = None
        self.stdout = None
        self.stderr = None
        self.return_code = None

    def setup(self, json_str: str):
        self.params = MotionCor2Input.parse_obj(json.loads(json_str))

    # def setup(self, json_str):
    #     input_data = json.loads(json_str)
    #     self.input_movie = input_data['input_movie']
    #     self.output_folder = input_data['output_folder']
    #     self.binning_factor = input_data.get('binning_factor', 1)

    def process(self):
        # Check if input movie file exists
        input_movie_path = Path(self.input_movie)
        if not input_movie_path.is_file():
            raise ValueError("Input movie file not found.")

        # Create output folder if it doesn't exist
        output_folder_path = Path(self.output_folder)
        if not output_folder_path.exists():
            output_folder_path.mkdir()

        #Build the command
        cmd= build_motioncor2_command(self.params)
        # Run MotionCor2 command
        command = f"MotionCor2 -InMrc {self.input_movie} -OutMrc {self.output_folder} " \
                  f"-Patch 5 5 -Gpu 0 -Bft {self.binning_factor}"
        process = subprocess.Popen(command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.stdout, self.stderr = process.communicate()
        self.return_code = process.returncode

        # Check if MotionCor2 ran successfully
        if self.return_code != 0:
            raise ValueError(f"MotionCor2 command failed with error: {self.stderr.decode()}")

        # Set output properties
        self.output_mrc = output_folder_path.joinpath(input_movie_path.stem + "_mrcs").as_posix()
        self.log_file = output_folder_path.joinpath(input_movie_path.stem + "_log.txt").as_posix()
