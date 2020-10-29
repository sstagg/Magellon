#!/usr/bin/env python

import os,sys
import optparse
import glob
from pyami import mrc
import numpy
from matplotlib import pyplot

#===============
def setupParserOptions():
	parser = optparse.OptionParser()
	parser.set_description("Calculate the autocorrelation of particles")
	parser.set_usage("%prog -s <stack file>")
	parser.add_option("-s", "--stack", type="string", metavar="FILE",
		help="stack file")
	parser.add_option("-d", "--dirname", type="string", metavar="DIRECTORY",
		help="directory containing stack files")
	parser.add_option("-e", "--ext", type="string", metavar="FILE EXTENSION",
		help="file extension for stack files (default='.mrcs')", default="mrcs")
	options,args = parser.parse_args()
	if len(args) > 0:
		parser.error("Unknown commandline options: " +str(args))
	if len(sys.argv) < 2:
		parser.print_help()
		parser.error("no options defined")
	params = {}
	for i in parser.option_list:
		if isinstance(i.dest, str):
			params[i.dest] = getattr(options, i.dest)
	return params

#===============
def checkConflicts(params):
	if not (params['stack'] or params['dirname']):
		exit("\nError: specify a stack file or directory\n")
	if (params['stack'] and params['dirname']):
		exit("\nSpecify either a stack or a directory\n")
	if params['stack']:
		params['stack']=os.path.abspath(params['stack'])
		if not os.path.exists(params['stack']):
			exit("\nError: specified stack '%s' does not exist\n"%params['stack'])
		params['stacks']=[params['stack']]
	if params['dirname']:
		params['dirname']=os.path.abspath(params['dirname'])
		if not os.path.exists(params['dirname']):
			exit("\nError: specified directory '%s' does not exist\n"%params['dirname'])
		params['stacks']=glob.glob(os.path.join(params['dirname'],"*."+params['ext']))
		if len(params['stacks']) == 0:
			exit("\nError: specified directory '%s' does not contain files with extension '%s'\n"%(params['dirname'],params['ext']))
	return params

#===============
def calcacorr(stackname, avg_acorr_out=False):
	particles=mrc.read(stackname)
	acorravg=numpy.zeros(shape=particles[0].shape, dtype=particles.dtype)
	print "calculating autocorrelation for %i particles in %s"%(len(particles),os.path.basename(stackname))
	for img in particles:
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
	
	acorravg=acorravg/particles.shape[0]
	acorravg=acorravg/acorravg.max()
	if avg_acorr_out:
		mrc.write(acorravg,avg_acorr_out)
	return acorravg


#===============
if  __name__ == "__main__":
	params = setupParserOptions()
	params = checkConflicts(params)
	
	for stack in params['stacks']:
		acorravg=calcacorr(stack)
		imgslice=acorravg[acorravg.shape[0]/2]
		pyplot.plot(imgslice, label=os.path.basename(stack))
	pyplot.legend(loc='upper right')
	pyplot.show()

