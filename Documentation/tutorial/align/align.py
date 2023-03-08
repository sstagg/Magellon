#!/usr/bin/env python

import sys
from pyami import correlator, peakfinder, convolver, mrc, imagefun
from appionlib.apImage import imagenorm
import numpy
import glob
import scipy

def getShift(ref,image,corr='cc', test=False, kernel=1):
	if corr=='cc':
		cc=correlator.cross_correlate(ref, image)
	elif corr=='pc':
		cc=correlator.phase_correlate(ref, image, zero=False)
		conv=convolver.Convolver()
		kernel=convolver.gaussian_kernel(kernel)
		conv.setKernel(kernel)
		cc=conv.convolve(image=cc)		
	if test is True:
		mrc.write(cc, 'cc.mrc')
	peak=peakfinder.findSubpixelPeak(cc)
	shift=correlator.wrap_coord(peak['subpixel peak'],ref.shape)
	#returns y,x
	#print shift
	return shift

def shiftParticle(image,shift, test=False):
	shifted=scipy.ndimage.shift(image, shift, mode='wrap', cval=0.0)
	if test is True:
		mrc.write(shifted,'shifted.mrc')
	return shifted

if __name__=='__main__':	
	proj=mrc.read("proj.mrc")
	rawnames=glob.glob("raw*.mrc")

	rawlist=[]
	for i in rawnames:
		img=mrc.read(i)
		#img=imagenorm.edgeNorm(img)
		rawlist.append(img)
		print "reading", i

	average=numpy.zeros(shape=proj.shape,dtype=proj.dtype)
	print "aligning!"
	for image in rawlist:
		shift=getShift(proj,image, corr='pc', test=True)
		average+=shiftParticle(image,shift, test=True)
	mrc.write(average,'avg.mrc')
	print "Done!"


