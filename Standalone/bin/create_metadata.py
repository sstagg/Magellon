import json
import mass_est_lib as mel
import mrcfile as mrc
import argparse
import sys

def create_json(sequence, filename="output.json"):
    data = {"mass": {f"img{i+1}": value for i, value in enumerate(sequence)}}

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stackpath", dest="stackpath", type=str, help="Path to stack")
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()

    return args


if __name__ == '__main__':

    args = parseArgs()
    stackheader=mrc.open(args.stackpath, header_only=True)
    apix=stackheader.voxel_size
    apix=apix.tolist()
    apix=apix[0]
    stackarray=mrc.read(args.stackpath)
    masses=[]

    for avg in stackarray:
        mass=int(round(mel.calc_mass(avg=avg, apix=apix, usebackground=True)/1000))
        masses.append(mass)

    create_json(masses)
        