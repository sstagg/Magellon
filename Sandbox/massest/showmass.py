#!/usr/bin/env python
import mass_est_lib as mel
import argparse
import sys
import mrcfile as mrc
from matplotlib import pyplot



def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stackpath", dest="stackpath", type=str, help="Path to stack")
    parser.add_argument("--showmasked", dest="showmasked", action='store_true', default=False, help="Show the masked averages")
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
        if args.showmasked is True:
            particlemask, backgroundmask=mel.make_masks_by_statistics(img=avg)
            mean, std=mel.get_edge_stats_for_box(avg,clippix=3)
            avg[backgroundmask]=mean
    fig = mel.create_montage_with_numbers(stackarray,numbers=masses)
    pyplot.show()