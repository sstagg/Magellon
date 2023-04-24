import os
import sys

from fastapi.testclient import TestClient

# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from main import app
from models.pydantic_plugins_models import MotionCor2Input
from services.motioncor2_service import MotionCor2Service, build_motioncor2_command

client = TestClient(app)


def test_build_command():
    # Create a new MotionCor2Params instance with default values
    params = MotionCor2Input()

    # Set specific parameter values
    params.InTiff = "/path/to/input.tiff"
    params.OutMrc = "/path/to/output.mrc"
    params.FtBin = 1.0
    params.Iter = 10
    params.Dark = "/path/to/dark.mrc"
    params.gain_file = "/path/to/gain1.mrc"

    # Print the parameter values
    print(
        params.dict())  # output: {'InTiff': '/path/to/input.tiff', 'OutMrc': '/path/to/output.mrc', 'FtBin': 1.0, 'Bft': [500, 100], 'Iter': 10, 'Tol': 0.5, 'Patch': [5, 5], 'Group': 1, 'MaskSize': [1.0, 1.0], 'FmDose': 0.0, 'PixSize': 0.0, 'kV': 0.0, 'Dark': '/path/to/dark.mrc', 'Gain': '/path/to/gain1.mrc', 'FlipGain': 0, 'RotGain': 0, 'Gpu': 0}

    # Generate the MotionCor2 command string
    cmd = build_motioncor2_command(params)
    print(cmd)


def test_build_command2():
    # params = MotionCor2Input(input_movie="movie.mrc", output_folder="output/", binning_factor=2)
    # params = MotionCor2Input()
    # Create a new MotionCor2Service instance
    mc2_service = MotionCor2Service(MotionCor2Input())

    # Load parameters from a JSON string
    json_str = '{"InTiff":"/gpfs/research/stagg/appiondata/23mar23b/ddstack/ddstack2' \
               '/23mar23b_a_00038gr_00003sq_v02_00008hl_v01_00002ex_st.tif",' \
               '"OutMrc":"temphpc-i36-5.local.gpuid_0_sum.mrc","FtBin":2.0,"Bft_global":500,"Bft_local":100,"Iter":7,"Tol":0.500,' \
               '"Patchrows":5,"Patchcols":5,"Group":1,"MaskSize":[1.000,1.000],"FmDose":0.645,"PixSize":0.705,"kV":300,' \
               '"Dark":"/gpfs/research/stagg/appiondata/23mar23b/ddstack/ddstack2/dark-hpc-i36-5-0.mrc",' \
               '"gain_file":' \
               '"/gpfs/research/stagg/framesdata/23mar23b/gain.mrc","FlipGain":0,"RotGain":0,"gpuids":"0"}'
    mc2_service.setup(json_str)

    # Generate the MotionCor2 command string
    cmd = build_motioncor2_command(mc2_service.params)

    # Print the command string
    print(
        cmd)  # output: motioncor2 -InTiff /gpfs/research/stagg/appiondata/23mar23b/ddstack/ddstack2/23mar23b_a_00038gr_00003sq_v02_00008hl_v01_00002ex_st.tif -OutMrc temphpc-i36-5.local.gpuid_0_sum.mrc -FtBin 2.0 -Bft 500.0 100.0 -Iter 7 -Tol 0.5 -Patch 5 5 -Group 1 -MaskSize 1.0 1.0 -FmDose 0.645 -PixSize 0.705 -kV 300.0 -Dark /gpfs/research/stagg/appiondata/23mar23b/ddstack/ddstack2/dark-hpc-i36-5-0.mrc -Gain /gpfs/research/stagg/appiondata/23mar23b/ddstack/ddstack2/norm-hpc-i36-5-0.mrc -Gain /gpfs/research/stagg/framesdata/23mar23b/gain.mrc -FlipGain 0 -RotGain 0 -Gpu 0
    assert cmd == "motioncor2 -InTiff /gpfs/research/stagg/appiondata/23mar23b/ddstack/ddstack2/23mar23b_a_00038gr_00003sq_v02_00008hl_v01_00002ex_st.tif -OutMrc temphpc-i36-5.local.gpuid_0_sum.mrc -FtBin 2.0 -Bft 500.0 100.0 -Iter 7 -Tol 0.5 -Patch 5 5 -Group 1 -MaskSize 1.0 1.0 -FmDose 0.645 -PixSize 0.705 -kV 300.0 -Dark /gpfs/research/stagg/appiondata/23mar23b/ddstack/ddstack2/dark-hpc-i36-5-0.mrc -Gain /gpfs/research/stagg/framesdata/23mar23b/gain.mrc -FlipGain 0 -RotGain 0 -Gpu 0"
