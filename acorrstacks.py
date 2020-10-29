#!/usr/bin/env python

from pyami import mrc
import numpy
import sys
from matplotlib import pyplot


def calcacorr(stackname, avg_acorr_out=False):
	i=mrc.read(stackname)
	acorravg=numpy.zeros(shape=i[0].shape, dtype=i.dtype)
	for img in i:
		#n+=1
		#print n
		I=numpy.fft.fftn(img)
		#I=numpy.fft.fftshift(I)
		Acorr=I * numpy.conjugate(I)
		#Acorr=numpy.fft.fftshift(Acorr)
		acorr=numpy.fft.ifftn(Acorr)
		acorr=acorr.real
		acorr=numpy.roll(acorr,acorr.shape[0]/2, axis=0)
		acorr=numpy.roll(acorr,acorr.shape[1]/2, axis=1)
		acorravg=acorravg+acorr
	
	acorravg=acorravg/i.shape[0]
	acorravg=acorravg/acorravg.max()
	if avg_acorr_out:
		mrc.write(acorravg,avg_acorr_out)
	return acorravg

stacks=sys.argv[1:]

for stack in stacks:
	acorravg=calcacorr(stack)
	slice=acorravg[acorravg.shape[0]/2]
	pyplot.plot(slice, label=stack)
pyplot.legend(loc='upper right')
pyplot.show()
