#!/usr/bin/env python
import glob
import numpy
import mass_est_lib as mel
import os
import argparse
import sys
import mrcfile as mrc
from matplotlib import pyplot


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
    border = 20

    stacks = glob.glob(os.path.join(args.stackpath, 'EMD*'))

    ### make dictionary of filenames and masses

    massdict = {}
    sums = []
    masses = []
    allsums = []
    allmasses = []
    for stack in stacks:
        print(stack)
        stackfile = os.path.join(stack, 'good', 'templates_selected.mrc')
        allavgstackfilename = glob.glob(os.path.join(stack, 'all', '*class_averages.mrc'))[0]
        stackheader = mrc.open(stackfile, header_only=True)
        apix = stackheader.voxel_size
        apix = apix.tolist()
        apix = apix[0]

        massfile = os.path.join(stack, 'mass.txt')
        f = open(massfile)
        lines = f.readlines()
        f.close()
        theoreticalmass = float(lines[0].split()[-1])
        experimentalmass = float(lines[1].split()[-1])
        stackarray = mrc.read(stackfile)
        for avg in stackarray:
            estmass = mel.calcMass(avg=avg, apix=apix, border=border)
            masses.append(theoreticalmass)
            sums.append(estmass)
            # print (experimentalmass, estmass)

        allstackarray = mrc.read(allavgstackfilename)
        for avg in allstackarray:
            estmass = mel.calcMass(avg=avg, apix=apix, border=border)
            allmasses.append(theoreticalmass)
            allsums.append(estmass)
            # print (experimentalmass, estmass)

    pyplot.plot(allmasses, allsums, 'ro')
    pyplot.plot(masses, sums, 'bo')
    pyplot.show()
    f=open("calibration.txt", 'w')
    for n,mass in enumerate(masses):
        avgsum=sums[n]
        f.write('%s\t%s\n' % (mass,avgsum))
    f.close()
    #
    # ### loop over the stacks and averages and estimate masses
    # for stackfile in stacks:
    #     filename=os.path.split(stackfile)[-1]
    #     stackroot=filename.split('.')[0].split('proj')[0]
    #     stack=mrc.read(stackfile)
    #     for n,avg in enumerate(stack):
    #         estmass = 0.5*mel.calcMass(avg=avg,apix=apix, border=border)
    #         # estmass = mel.calcMass(avg=avg,apix=apix, border=border)
    #         print ("Estimated mass for avg %d from file %s is %d kDa" % (n, stackroot, estmass))
    #         sums.append(estmass)
    #         masses.append(massdict[stackroot])
    #
    # # Perform linear fit
    # coeffs = numpy.polyfit(masses, sums, 1)
    # linear_fit = numpy.poly1d(coeffs)
    #
    # # Create a linear fit line
    # fit_line = linear_fit(masses)
    #
    # # Plot the data points and the linear fit
    # pyplot.plot(masses, sums, 'bo', label='Data')
    # pyplot.plot(masses, fit_line, 'r-', label=f'Linear Fit: y = {coeffs[0]:.2f}x + {coeffs[1]:.2f}')
    # pyplot.xlabel('Mass')
    # pyplot.ylabel('Estimated Mass')
    # pyplot.legend()
    # pyplot.title('Linear Fit of Mass Estimation Data')
    # pyplot.show()
