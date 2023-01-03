#!/usr/bin/env python

from leginon import leginondata

def getImageData(imgname):
	"""
	get image data object from database
	"""
	imgquery = leginondata.AcquisitionImageData(filename=imgname)
	imgtree  = imgquery.query(results=1, readimages=False)
	if imgtree:
		return imgtree[0]
	else:
		apDisplay.printError("Image "+imgname+" not found in database\n")

#================
def getPixelSize(imgdata):
	"""
	use image data object to get pixel size
	multiplies by binning and also by 1e10 to return image pixel size in angstroms
	shouldn't have to lookup db already should exist in imgdict

	return image pixel size in Angstroms
	"""
	pixelsizeq = leginondata.PixelSizeCalibrationData()
	pixelsizeq['magnification'] = imgdata['scope']['magnification']
	pixelsizeq['tem'] = imgdata['scope']['tem']
	pixelsizeq['ccdcamera'] = imgdata['camera']['ccdcamera']
	pixelsizedatas = pixelsizeq.query()

	if len(pixelsizedatas) == 0:
		apDisplay.printError("No pixelsize information was found image %s\n\twith mag %d, tem id %d, ccdcamera id %d"
			%(imgdata['filename'], imgdata['scope']['magnification'],
			imgdata['scope']['tem'].dbid, imgdata['camera']['ccdcamera'].dbid)
		)

	### check to get one before image was taken
	i = 0
	pixelsizedata = pixelsizedatas[i]
	oldestpixelsizedata = pixelsizedata
	while pixelsizedata.timestamp > imgdata.timestamp and i < len(pixelsizedatas):
		i += 1
		pixelsizedata = pixelsizedatas[i]
		if pixelsizedata.timestamp < oldestpixelsizedata.timestamp:
			oldestpixelsizedata = pixelsizedata
	if pixelsizedata.timestamp > imgdata.timestamp:
		apDisplay.printWarning("There is no pixel size calibration data for this image, using oldest value")
		pixelsizedata = oldestpixelsizedata
	binning = imgdata['camera']['binning']['x']
	pixelsize = pixelsizedata['pixelsize'] * binning
	return(pixelsize*1e10)

#================
def getDoseFromImageData(imgdata):
	''' returns dose, in electrons per Angstrom '''
	try:
		dose = imgdata['preset']['dose']
		return dose / 1e20
	except:
		# fails either because no preset or no dose
		# apDisplay.printWarning("dose not available for this image")
		return None

if __name__ == '__main__':
	#getImageData('22apr01a_a_00010gr_00001sq_v01_00002hl_00006ex-b_v02')
	getImageData('22apr01a_b_00011gr_00021sq_v01_00028hl')