import json
import subprocess
from typing import List


class CTFService:
    def __init__(self):
        self.input_micrographs = []
        self.output_folder = ""
        self.pixel_size = 0.0
        self.defocus_range = []
        self.astigmatism_range = []
        self.amplitude_contrast = 0.1
        self.box_size = 256
        self.output_star = ""
        self.output_plot = ""

    def setup(self, input_json: str):
        input_data = json.loads(input_json)
        self.input_micrographs = input_data["input_micrographs"]
        self.output_folder = input_data["output_folder"]
        self.pixel_size = input_data["pixel_size"]
        self.defocus_range = input_data["defocus_range"]
        self.astigmatism_range = input_data["astigmatism_range"]
        self.amplitude_contrast = input_data.get("amplitude_contrast", 0.1)
        self.box_size = input_data.get("box_size", 256)

    def process(self):
        input_files = " ".join(self.input_micrographs)
        cmd = f"ctffind4 {input_files} --star {self.output_folder}/ctf.star " \
              f"--plot {self.output_folder}/ctf.pdf " \
              f"--boxsize {self.box_size} " \
              f"--pixelsize {self.pixel_size} " \
              f"--defocus {self.defocus_range[0]},{self.defocus_range[1]} " \
              f"--dStep {self.astigmatism_range[0]},{self.astigmatism_range[1]} " \
              f"--ampconst {self.amplitude_contrast}"
        subprocess.run(cmd, shell=True, check=True)

        self.output_star = f"{self.output_folder}/ctf.star"
        self.output_plot = f"{self.output_folder}/ctf.pdf"
