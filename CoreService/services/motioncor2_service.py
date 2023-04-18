import json
import subprocess
import os
from pathlib import Path


class MotionCor2Service:
    def __init__(self):
        self.log_file = None
        self.output_mrc = None
        self.input_movie = None
        self.output_folder = None
        self.binning_factor = None
        self.stdout = None
        self.stderr = None
        self.return_code = None

    def setup(self, json_str):
        input_data = json.loads(json_str)
        self.input_movie = input_data['input_movie']
        self.output_folder = input_data['output_folder']
        self.binning_factor = input_data.get('binning_factor', 1)

    def process(self):
        # Check if input movie file exists
        input_movie_path = Path(self.input_movie)
        if not input_movie_path.is_file():
            raise ValueError("Input movie file not found.")

        # Create output folder if it doesn't exist
        output_folder_path = Path(self.output_folder)
        if not output_folder_path.exists():
            output_folder_path.mkdir()

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
