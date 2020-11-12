#!/usr/bin/env python

from pyami import mrc
from pyami import imagefun
import sys
import numpy
import argparse

#density for protein is 0.81 Da/A^3
densityarea=(0.81**(1/3.0))**2

def getEdgeStatsForBox(img,clippix):
	edgepix=img[clippix:-clippix,clippix]
	edgepix=numpy.append(edgepix, img[clippix:-clippix,-clippix])
	edgepix=numpy.append(edgepix, img[clippix,clippix:-clippix ])
	edgepix=numpy.append(edgepix, img[-clippix,clippix:-clippix ])
	mean=edgepix.mean()
	std=edgepix.std()
	return mean, std

def sumPixelsAboveThreshold(mean=None, std=None, nstd=3, img=None):
	boolarray=img > mean+std*nstd
	img=img-mean
	#scaled=img/(mean+std*nstd)
	pixelsum=numpy.sum(img[boolarray])
	#pixelsum=numpy.sum(scaled[boolarray])
	return pixelsum

def setupParserOptions():
	#note using argparse because optparse is deprecated
	parser=argparse.ArgumentParser(description="A program to estimate the masses of 2D class averages") 
	parser.add_argument('--apix', type=float, default=1.0, help="Pixel size in Angstroms for the stack")
	parser.add_argument('stack', type=str, nargs=1, help="Stack containing class averages for mass estimation")
	args=parser.parse_args()
	return args
	


if __name__=='__main__':
	
	args=setupParserOptions()
	#arbscale=14.262714475930819		
	arbscale=1/5.0		
	avgarray=mrc.read(args.stack[0])
	border=20
	
	for n,avg in enumerate(avgarray):
		mean,std=getEdgeStatsForBox(avg,border)
		pixsum=sumPixelsAboveThreshold(mean=mean, std=std, img=avg)
		angsum=pixsum*args.apix**2
		estmass=angsum*arbscale
		print "Estimated mass for avg %d is %d kDa" % (n,estmass)
		

