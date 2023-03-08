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
	#=====================
	def setupParserOptions(self):
		self.parser.add_option("--dryrun", dest="dryrun", default=False, action='store_true', help="Just show files that will be deleted, but do not delete them.")
		self.parser.add_option("--filterradius", dest="filterradius", default=3, type=float, help="Sigma for Gaussian lowpass filter")

	#=====================
	def checkConflicts(self):
		if self.params['dryrun'] is True:
			self.params['commit']=False
			self.params['no-continue']=True
			
	def preLoopFunctions(self):
		pass
		
	def processImage(self, imgdata):
		filtered=imagefilter.lowPassFilter(imgdata['image'], radius=self.params['filterradius'])
		if self.params['dryrun'] is True:
			mrc.write(filtered,'filtered.mrc') # apDBImage.makeAlignedImageData writes out the image otherwise			
			return None
		else:
			camdata=imgdata['camera']
			newimagedata=apDBImage.makeAlignedImageData(imgdata,camdata,filtered,"lw")
			newname=newimagedata['filename']
			results=newimagedata
			#print results
			return results

	#=====================
	def loopCommitToDatabase(self, imgdata):
		pass
	
	def commitResultsToDatabase(self, imgdata, results):
		"""
		put in any additional commit parameters
		"""
		if results is not None:
			results.insert()
	

#=====================
#=====================
if __name__ == '__main__':
	lowpassFilter = LowPassLoop()
	lowpassFilter.run()

