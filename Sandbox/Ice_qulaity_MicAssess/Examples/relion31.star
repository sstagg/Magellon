# RELION 3.1 star file with an optics-group block.
# micassess reads only _rlnMicrographName from the data_micrographs block;
# the optics block is carried along so the output star files stay RELION 3.1-compatible.
#
# Usage:
#   micassess -i examples/relion31.star -m weights/

data_optics

loop_
_rlnOpticsGroup                 #1
_rlnOpticsGroupName             #2
_rlnAccumMotionTotal            #3
_rlnMicrographOriginalPixelSize #4
_rlnVoltage                     #5
_rlnSphericalAberration         #6
_rlnAmplitudeContrast           #7
_rlnMicrographPixelSize         #8
1  opticsGroup1  0.000000  0.832000  300.000000  2.700000  0.100000  0.832000


data_micrographs

loop_
_rlnMicrographName  #1
_rlnOpticsGroup     #2
micrographs/session_001.mrc  1
micrographs/session_002.mrc  1
micrographs/session_003.mrc  1
