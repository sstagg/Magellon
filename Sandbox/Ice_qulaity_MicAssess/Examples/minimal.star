# Minimal RELION star file accepted by micassess.
# Each line under _rlnMicrographName is a path to one .mrc file.
# Paths are relative to the directory where you run micassess.
#
# Usage:
#   micassess -i examples/minimal.star -m weights/

data_

loop_
_rlnMicrographName
micrographs/session_001.mrc
micrographs/session_002.mrc
micrographs/session_003.mrc
