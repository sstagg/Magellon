#!/usr/bin/env python
import mass_est_lib as mel
import argparse
import sys
import mrcfile as mrc
from matplotlib import pyplot



def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stackpath", dest="stackpath", type=str, help="Path to stack")
    parser.add_argument("--writemasked", dest="writemasked", type=str, default=None, help="Write out a masked stack with the given name, e.g. '--writemasked out.mrc'. Default is no output")
    parser.add_argument("--nomask", dest="nomask", action='store_true', default=False, help="Don't apply the mask")
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
    if args.nomask is not True:
        for avg in stackarray:
            particlemask, backgroundmask=mel.make_masks_by_statistics(img=avg)
            mean, std=mel.get_edge_stats_for_box(avg,clippix=3)
            avg[backgroundmask]=mean
        if args.writemasked is not None:
            mrc.write(args.writemasked, stackarray, overwrite=True)
    fig = mel.create_montage_with_numbers(stackarray)
    pyplot.show()
