#!/usr/bin/env python

import os
import sys
import glob
import shutil
import subprocess
import time
from appionlib import apDisplay
from appionlib import appionLoop2
from appionlib import apDatabase
from pyami import mrc
from appionlib.apImage import imagefilter
import leginon.leginondata as leginondata

#=====================
	
class LowPassLoop(appionLoop2.AppionLoop):
	#=====================
	def setupParserOptions(self):
		self.parser.add_option("--dryrun", dest="dryrun", default=False, action='store_true', help="Just show files that will be deleted, but do not delete them.")
		self.parser.add_option("--filterradius", dest="filterradius", default=3, type=float, help="Sigma for Gaussian lowpass filter")

	#=====================
	def checkConflicts(self):
		if self.params['dryrun'] is True:
			self.params['commit']=False
			
	def preLoopFunctions(self):
		pass
		
	def processImage(self, imgdata):
		filtered=imagefilter.lowPassFilter(imgdata['image'], radius=self.params['filterradius'])
		mrc.write(filtered,'filtered.mrc')
		results=None
		return results

	#=====================
	def loopCommitToDatabase(self, imgdata):
		pass
	
	def commitResultsToDatabase(self, imgdata, results):
		"""
		put in any additional commit parameters
		"""
		pass
	

#=====================
#=====================
if __name__ == '__main__':
	lowpassFilter = LowPassLoop()
	lowpassFilter.run()

