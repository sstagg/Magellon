#!/usr/bin/env python

import sys
from pyami import correlator, peakfinder, convolver, mrc, imagefun
from appionlib.apImage import imagenorm #optional for normalizing raw images
import numpy
import glob
import scipy

#read projection and raw images using mrc.read()

#loop through all raw images to shift them to the center and average them

#optionally normalize raw images before correlating

#find shifts with cross correlation or phase correlation using correlator.cross_correlate() or correlator.phase_correlate

#find peaks in cc image using peakfinder.findSubpixelPeak()

#findSubpixelPeak returns a dictionary where 'subpixel peak' is the keyword for the coordinates of the peak

#the origin in the cc image is at the corners, so to determine the actual shift, the coordinates need to be wrapped to the center

#use correlator.wrap_coord to wrap the coordinates to the center to determine actual shift

#use scipy.ndimage.shift to shift images to center

#write out the average with mrc.write()

