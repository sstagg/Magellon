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
	parser.add_option("--combine", action="store_true", help="combine all stacks into 1 output")
	parser.add_option("--legend", action="store_true", help="include a legend in the plot")
	parser.add_option("--savefig", type="string", default=None, help="save figure instead of showing")
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
def calcacorr(stackname, avg_acorr_out=False, startingAvg=None):
	particles=mrc.read(stackname)
	if startingAvg is None:
		acorravg=numpy.zeros(shape=particles[0].shape, dtype=particles.dtype)
	else:
		acorravg = startingAvg
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
	
	if startingAvg is None:
		acorravg=acorravg/len(particles)
		acorravg=acorravg/acorravg.max()
	if avg_acorr_out:
		mrc.write(acorravg,avg_acorr_out)

	return acorravg,len(particles)


#===============
if  __name__ == "__main__":
	params = setupParserOptions()
	params = checkConflicts(params)
	
	runningavg = None
	totalparticles = 0
	if params['combine'] is True:
		totalParticles = 0
		# read the first particle of the first stack to get a size
		particle = mrc.read(params['stacks'][0],0)
		runningavg = numpy.zeros(shape=particle.shape, dtype=particle.dtype)
		print runningavg.shape
	
	for stack in params['stacks']:
		acorravg,pnum=calcacorr(stack, startingAvg=runningavg)
		totalparticles+=pnum
		if params['combine'] is True:
			runningavg += acorravg
			continue

		imgslice=acorravg[acorravg.shape[0]/2]
		pyplot.plot(imgslice, linewidth=2, label=os.path.basename(stack).split('.')[0])

	if params['combine'] is True:
		runningavg=runningavg/totalparticles
		runningavg=runningavg/runningavg.max()
		imgslice=runningavg[runningavg.shape[0]/2]
		pyplot.plot(imgslice, linewidth=1, label="all stacks")
		
	if params['legend'] is True:
		pyplot.legend(loc='upper right')
	
	fontsize=20
	pyplot.xticks(fontsize=fontsize)
	pyplot.yticks(fontsize=fontsize)
	pyplot.xlabel("Pixels",fontsize=fontsize)
	pyplot.ylabel("Correlation",fontsize=fontsize)
	if params['savefig'] is not None:
		pyplot.savefig(params['savefig'])
	else:
		pyplot.show()

