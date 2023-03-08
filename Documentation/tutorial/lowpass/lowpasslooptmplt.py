#!/usr/bin/env python

import os
import sys
import glob
from appionlib import apDisplay
from appionlib import appionLoop2
from appionlib import apDatabase
from appionlib import apDBImage
from pyami import mrc
from appionlib.apImage import imagefilter

#=====================
	
class LowPassLoop(appionLoop2.AppionLoop):
	### All classes that inherit AppionLoop will need the functions below.
	### AppionLoop children will inherit a "run" method that will loop over all of the images for a given session
	### AppionLoop children will gain a large number of commonly used options that you will extend with setupParserOptions in this script
	#=====================
	def setupParserOptions(self):
		# add script specific options
		self.parser.add_option("--filterradius", dest="filterradius", default=3, type=float, help="Sigma for Gaussian lowpass filter")

	#=====================
	def checkConflicts(self):
		# check for conflicts in command line options. In my example, I have a "dryrun" option where I want it to have a certain behavior that I set up here
		if self.params['dryrun'] is True:
			self.params['commit']=False
			self.params['no-continue']=True
			
	def preLoopFunctions(self):
		# function is required but doesn't need to do anything
		pass
		
	def processImage(self, imgdata):
		#this is the heart of the program
		# if you're uploading results to the database, the db parameters should be returned in the return statement
		# use the imagefilter.lowPassFilter method (or similar) to lowpass filter the images
		return None

	#=====================
	def loopCommitToDatabase(self, imgdata):
		# required for historical purposes
		pass
	
	def commitResultsToDatabase(self, imgdata, results):
		# This is where you upload results to the database
		# As you can see if you return None in processImage, it won't do anything
		if results is not None:
			results.insert()
	

#=====================
#=====================
if __name__ == '__main__':
	lowpassFilter = LowPassLoop()
	lowpassFilter.run()

