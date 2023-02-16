#!/usr/bin/env python

import os
import sys
from pyami import mrc
from appionlib.apImage import imagefilter
import optparse

def parseOptions():
	parser=optparse.OptionParser()
	parser.add_option('-i', dest='i', type='str', help='input mrc file')
	parser.add_option('-o', dest='o', type='str', help='out mrc file')
	parser.add_option('--lp', dest='lp', type='float', default=3, help='low pass filter radius')

	options, args=parser.parse_args()

	if len(args) != 0 or len(sys.argv) == 1:
		parser.print_help()
		sys.exit()

	return options

if __name__ == '__main__':

	options=parseOptions()
	inmrc=mrc.read(options.i)
	print ("Filtering",options.i)
	filtered=imagefilter.lowPassFilter(inmrc, radius=options.lp)
	mrc.write(filtered,options.o)
	
