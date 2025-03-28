import DECameraClientLib
import numpy
import time
import pyami.imagefun
import ccdcamera
import threading
from pyami import moduleconfig

# frame flipping configuration.
# default here is for DE-20 orientation on JEM-3200FSC
FRAME_LR_FLIP = True
# frame rotate configuration. multiple of 90 degrees if needed
# after the flip.  Direction + is x to -y.
FRAME_ROTATE = -1 
# always use all available frames
USE_ALL_FRAMES = True

# Shared global connection to the DE Server
__deserver = None
__active_camera = None
__deserver_lock = threading.RLock()

## decorator to put a thread lock around a function
def locked(fun):
	def newfun(*args, **kwargs):
		__deserver_lock.acquire()
		try:
			return fun(*args, **kwargs)
		finally:
			__deserver_lock.release()
	return newfun

##### Begin thread safe functions to operate on DE Server #####

@locked
def de_connect():
	global __deserver
	if __deserver:
		return
	__deserver = DECameraClientLib.DECameraClientLib()
	__deserver.connect()

@locked
def de_disconnect():
	global __deserver
	if __deserver.connected:
		__deserver.disconnect()

@locked
def de_setActiveCamera(de_name):
	global __deserver
	global __active_camera
	if __active_camera != de_name:
		__deserver.setActiveCamera(de_name)
		__active_camera = de_name

@locked
def de_print_props(de_name):		
	global __deserver
	de_setActiveCamera(de_name)
	camera_properties = __deserver.getActiveCameraProperties()
	for one_property in camera_properties:
		print one_property, __deserver.getProperty(one_property)		

@locked
def de_getProperty(de_name, name):		
	global __deserver
	de_setActiveCamera(de_name)
	value = __deserver.getProperty(name)
	return value

@locked
def de_setProperty(de_name, name, value):		
	global __deserver
	de_setActiveCamera(de_name)
	value = __deserver.setProperty(name, value)
	return value

@locked
def de_getDictProp(de_name, name):		
	global __deserver
	de_setActiveCamera(de_name)
	x = int(__deserver.getProperty(name + ' X'))
	y = int(__deserver.getProperty(name + ' Y'))
	return {'x': x, 'y': y}

@locked
def de_setDictProp(de_name, name, xydict):		
	global __deserver
	de_setActiveCamera(de_name)
	__deserver.setProperty(name + ' X', int(xydict['x']))
	__deserver.setProperty(name + ' Y', int(xydict['y']))		

@locked
def de_getImage(de_name):
	global __deserver
	de_setActiveCamera(de_name)
	image = __deserver.GetImage()
	return image

##### End thread safe functions to operate on DE Server #####

deconfigs = moduleconfig.getConfigured('de.cfg')

class DECameraBase(ccdcamera.CCDCamera):
	'''
	All DE camera classes should inherit this to allow
	for a shared connection to the DE server.
	Subclasses should define an attribute "de_name"
	to inform this base class how to set the active camera.
	'''
	logged_methods_on = False
	def __init__(self):
		ccdcamera.CCDCamera.__init__(self)

		de_connect()

		## instance specific 
		self.offset = {'x': 0, 'y': 0}
		self.binning = {'x': 1, 'y': 1}
		self.dimension = self._getCameraSize()

		#update a few essential camera properties to default values
		self.setProperty('Correction Mode', 'Uncorrected Raw')
		self.setProperty('Image Size X', self.dimension['x'])
		self.setProperty('Image Size Y', self.dimension['y'])
		self.setProperty('ROI Dimension X', self.dimension['x'])
		self.setProperty('ROI Dimension Y', self.dimension['y'])
		self.setProperty('ROI Offset X', 0)
		self.setProperty('ROI Offset Y', 0)

	def getDEConfig(self, optionname, itemname=None):
		if itemname is None:
			return deconfigs[optionname]
		else:
			return deconfigs[optionname][itemname]

	def getProperty(self, name):
		value = de_getProperty(self.model_name, name)
		return value

	def setProperty(self, name, value):
		value = de_setProperty(self.model_name, name, value)
		return value

	def getDictProp(self, name):
		return de_getDictProp(self.model_name, name)

	def setDictProp(self, name, xydict):
		return de_setDictProp(self.model_name, name, xydict)

	def _getImage(self):
		old_frames_name = self.getPreviousRawFramesName()
		#self.custom_setup()
		t0 = time.time()
		image = de_getImage(self.model_name)
		t1 = time.time()
		#self.postAcquisitionSetup()
		self.exposure_timestamp = (t1 + t0) / 2.0
		if not isinstance(image, numpy.ndarray):
			raise ValueError('GetImage did not return array')
		image = self.finalizeGeometry(image)
		## wait for frames name to be updated before returning
		if self.getSaveRawFrames():
			new_frames_name = self.getPreviousRawFramesName()
			while not new_frames_name or (new_frames_name == old_frames_name):
				time.sleep(1.0)
				new_frames_name = self.getPreviousRawFramesName()
		print('----')
		return image

	def _getCameraSize(self):
		return self.getDictProp('Sensor Size')

	def getExposureTime(self):
		seconds = self.getProperty('Exposure Time (seconds)')
		ms = int(seconds * 1000.0)
		return ms

	def setExposureTime(self, ms):
		seconds = ms / 1000.0
		self.setProperty('Exposure Time (seconds)', seconds)

	def getDimension(self):
		return self.dimension

	def setDimension(self, dimdict):
		self.dimension = dimdict
	
	def getBinning(self):
		return self.binning

	def setBinning(self, bindict):
		self.binning = bindict

	def getOffset(self):
		return self.offset

	def setOffset(self, offdict):
		self.offset = offdict

	def finalizeGeometry(self, image):
		# DE camera offsets and dimensions are not sent to
		# the camera but are handled in this function.
		row_start = self.offset['y'] * self.binning['y']
		col_start = self.offset['x'] * self.binning['x']
		nobin_rows = self.dimension['y'] * self.binning['y']
		nobin_cols = self.dimension['x'] * self.binning['x']
		row_end = row_start + nobin_rows
		col_end = col_start + nobin_cols
		nobin_image = image[row_start:row_end, col_start:col_end]
		assert self.binning['x'] == self.binning['y']
		binning = self.binning['x']
		## NOTE:  non-standard binning: mean, not sum
		## See method getBinnedMultiplier below.
		bin_image = pyami.imagefun.bin(nobin_image, binning)
		return bin_image

	def getBinnedMultiplier(self):
		'''
		DE software binning calculates a binned pixel
		as the average of the component pixels, which is
		different that typical hardware binning.  This will
		return a multiplier that can be used to calculate
		a "standard" binned pixel.
		'''
		return self.binning['x'] * self.binning['y']

	def getPixelSize(self):
		psize = 6e-6
		return {'x': psize, 'y': psize}

	def getRetractable(self):
		return True
		
	def setInserted(self, value):
		# return if already at this insertion state
		if not (value ^ self.getInserted()):
			return
		if value:
			de12value = 'Extended'
			sleeptime = 20
		else:
			de12value = 'Retracted'
			sleeptime = 8
		self.setProperty("Camera Position", de12value)
		time.sleep(sleeptime)
		
	def getInserted(self):
		de12value = self.getProperty('Camera Position Status')
		return de12value == 'Extended'

	def getExposureTypes(self):
		return ['normal','dark']

	def getExposureType(self):
		exposure_type = self.getProperty('Exposure Mode')		
		return exposure_type.lower()
		
	def setExposureType(self, value):		
		self.setProperty('Exposure Mode', value.capitalize()) 

	def getNumberOfFrames(self):
		result = self.getProperty('Total Number of Frames')
		#print 'number of frames:', result
		return result

	def getSaveRawFrames(self):
		'''Save or Discard'''
		value = self.getProperty('Autosave Raw Frames')
		if value == 'Save':
			return True
		elif value == 'Discard':
			return False
		else:
			raise ValueError('unexpected value from Autosave Raw Frames: %s' % (value,))

	def setSaveRawFrames(self, value):
		'''True: save frames,  False: discard frames'''
		if value:
			value_string = 'Save'
		else:
			value_string = 'Discard'
		self.setProperty('Autosave Raw Frames', value_string)

	def getPreviousRawFramesName(self):
		frames_name = self.getProperty('Autosave Frames - Previous Dataset Name')
		return frames_name
		
	def getNumberOfFramesSaved(self):
		nframes = self.getProperty('Autosave Raw Frames - Frames Written in Last Exposure')
		return int(nframes)

	def getUseFrames(self):
		nsum = self.getProperty('Autosave Sum Frames - Sum Count')
		first = self.getProperty('Autosave Sum Frames - Ignored Frames')
		last = first + nsum
		ntotal = self.getNumberOfFrames()
		if last > ntotal:
			last = ntotal
		sumframes = range(first,last)
		return tuple(sumframes)

	def setUseFrames(self, frames):
		total_frames = self.getNumberOfFrames()
		if USE_ALL_FRAMES:
			frames = None
		if frames:
			nskip = frames[0]
			last = frames[-1]
		else:
			nskip = 0
			last = total_frames - 1
		nsum = last - nskip + 1
		if nsum > total_frames:
			nsum = total_frames
		nsum = int(nsum)
		self.setProperty('Autosave Sum Frames - Sum Count', nsum)
		self.setProperty('Autosave Sum Frames - Ignored Frames', nskip)

	def getFrameTime(self):
		fps = self.getProperty('Frames Per Second')
		ms = (1.0 / fps) * 1000.0
		print 'frametime', ms
		return ms

	def setFrameTime(self, ms):
		seconds = ms / 1000.0
		fps = 1.0 / seconds
		self.setProperty('Frames Per Second', fps)

	def getSaveLzwTiffFrames(self):
		# Lzw Tiff file saving for frames
		return True

	def getReadoutDelay(self):
		return self.getProperty('Sensor Readout Delay (milliseconds)')

	def setReadoutDelay(self, milliseconds):
		self.setProperty('Sensor Readout Delay (milliseconds)', milliseconds)

	def getTemperatureStatus(self):
		return self.getProperty('Temperature Control')

	## method name altered to prevent Leginon from setting temperature
	def set_TemperatureStatus(self, state):
		return self.setProperty('Temperature Control', state)

	def getTemperature(self):
		return self.getProperty('Temperature - Detector (Celsius)')

	def set_Temperature(self, degrees):
		return self.setProperty('Temperature Control - Setpoint (Celsius)', degrees)

#### Classes for specific cameras

class DE12Survey(DECameraBase):
	name = 'DE12 Survey'
	model_name = 'DE12 Survey'
	def __init__(self):
		DECameraBase.__init__(self)
		self.dimension = {'x': 1024, 'y': 1024}

class DE20Survey(DECameraBase):
	name = 'DE20 Survey'
	model_name = 'DE20 Survey'
	def __init__(self):
		DECameraBase.__init__(self)
		self.dimension = {'x': 2048, 'y': 1920}
		
	def custom_setup(self):
		pass

class DD(DECameraBase):
	name = 'DD'
	model_name = 'DD'
	def __init__(self):
		'''
		DD camera
		'''
		# Keep the proxy object to be used later
		# to avoid "not an instance of the module problem
		# after reload.
		self.as_super = super(DD,self)

		self.as_super.__init__()
		self.setProperty('Ignore Number of Frames', 0)
		self.default_frametime = 40
		self.requestnframes = 1
		self.setFrameTime(self.default_frametime)
		frame_time_ms = self.getFrameTime()
		self.setProperty('Preexposure Time (seconds)', frame_time_ms/1000.0)

	def finalizeGeometry(self, image):
		image = self.as_super.finalizeGeometry(image)
		if self.getFrameFlip() and self.getFrameRotate() == 2:
			image = numpy.fliplr(image)
		return image

	def getFrameFlip(self):
		'''
		Frame Flip is defined as up-down flip
		'''
		return FRAME_LR_FLIP

	def getCalculateNormFromDark(self):
		return False

	def getRequireRecentDarkOnBright(self):
		return True

	def getFrameRotate(self):
		'''
		Frame Rotate direction is defined as x to -y rotation applied after up-down flip
		'''
		return FRAME_ROTATE + 2

	def setElectronCounting(self, state):
		#self.setProperty('Electron Counting', state)
		pass

	def getElectronCounting(self):
		return False
		#return self.getProperty('Electron Counting')

	def setSensorHardwareBinning(self, state):
		self.setProperty('Sensor Hardware Binning', state)

	def getSensorHardwareBinning(self):
		return self.getProperty('Sensor Hardware Binning')

	def setHardwareBinning(self, value):
		self.setProperty('Binning X', value)
		self.setProperty('Binning Y', value)

	def getHardwareBinning(self):
		x = self.getProperty('Binning X')
		y = self.getProperty('Binning Y')
		return {'x': x, 'y': y}

	def setECApplyCountingGain(self, state):
		self.setProperty('Electron Counting - Apply Post-Counting Gain', state)

	def getECApplyCountingGain(self):
		return self.getProperty('Electron Counting - Apply Post-Counting Gain')

	def setFramesPerSecond(self, value):
		self.setProperty('Frames Per Second', value)

	def getFramesPerSecond(self):
		return self.getProperty('Frames Per Second')

	#def setECDoseFractionationNumberFrames(self, name):
	#	value = self.getDEConfig(name, 'dose_fractionation_number_of_frames')
	#	self.setProperty('Electron Counting - Dose Fractionation Number of Frames', value)

	def getECDoseFractionationNumberFrames(self):
		return self.getProperty('Electron Counting - Dose Fractionation Number of Frames')

	#def setECThreshold(self, name):
	#	value = self.getDEConfig(name, 'threshold')
	#	self.setProperty('Electron Counting - Threshold', value)

	def getECThreshold(self):
		return self.getProperty('Electron Counting - Threshold')

	def countingSetUp(self):
		binvalue = self.getDEConfig(self.name, 'binning')
		frameratevalue = self.getDEConfig(self.name, 'frames_per_second')
		self.setHardwareBinning(binvalue)
		self.setFramesPerSecond(frameratevalue)
		self.setElectronCounting('Enable')
		self.setECApplyCountingGain('Enable')
		self.setProperty('Correction Mode', 'Dark Corrected')
		self.setProperty('Autosave Raw Frames', 'Discard')
		self.setProperty('Electron Counting - Apply Post-Counting Gain', 'Enable')
		self.setProperty('Electron Counting - Apply Post-Threshold Gain', 'Enable')
		self.setProperty('Electron Counting - Fourier Filter Final', 'Enable')
		self.setProperty('Electron Counting - Fourier Filter Movie', 'Enable')

	def setRequestNFrames(self, value):
		self.requestnframes = value

	def getRequestNFrames(self):
		return self.requestnframes

	def setCalculatedFractionNumber(self):
		# Calculation for the Fractionation Number for movie creation
		numframes = self.getRequestNFrames()
		seconds = self.getProperty('Exposure Time (seconds)')
		ms = int(seconds * 1000.0)
		fps = self.getFramesPerSecond()
		fpms = fps / 1000.0
		baseframetime = 1 / fpms
		nfractionation = int(round(ms / (baseframetime * numframes)))
		self.setProperty('Electron Counting - Dose Fractionation Number of Frames', nfractionation)

	def postAcquisitionSetup(self):
		# It resets the movie frame time to its original value
		nfractionation = self.getECDoseFractionationNumberFrames()
		frame_time_ms = self.getFrameTime() * nfractionation
		self.setFrameTime(frame_time_ms)

class DE12(DD):
	name = 'DE12'
	model_name = 'DE12'

class DE20(DD):
	name = 'DE20'
	model_name = 'DE20'
	def getPixelSize(self):
		psize = 6.4e-6
		return {'x': psize, 'y': psize}

	def custom_setup(self):
		'''DE20 Integration specific camera setting'''
		self.setElectronCounting('Disable')
		binvalue = self.getDEConfig(self.name, 'binning')
		self.setHardwareBinning(binvalue)
		#v1.0 missing these
		#self.setECApplyCountingGain('Disable')
		#self.setProperty('Electron Counting - Dose Fractionation Number of Frames', 1)

class DE20c(DD):
	name = 'DE20c'
	model_name = 'DE20'
	def getPixelSize(self):
		psize = 6.4e-6
		return {'x': psize, 'y': psize}

	def getSystemGainDarkCorrected(self):
		return True

	def custom_setup(self):
		'''DE20 Counting specific camera setting'''
		self.countingSetUp()
		self.setCalculatedFractionNumber()

	def getSaveRawFrames(self):
		'''Save or Discard'''
		value = self.getProperty('Autosave Movie')
		if value == 'Save':
			return True
		elif value == 'Discard':
			return False
		else:
			raise ValueError('unexpected value from Autosave Raw Frames: %s' % (value,))

	def setSaveRawFrames(self, value):
		'''DE20 True: save frames,  False: discard frames'''
		if value:
			value_string = 'Save'
		else:
			value_string = 'Discard'
		self.setProperty('Autosave Movie', value_string)

class DE64(DD):
	name = 'DE64'
	model_name = 'DE64'
	def getPixelSize(self):
		psize = 6.5e-6
		return {'x': psize, 'y': psize}
	def getFrameRotate(self):
		'''
		Frame Rotate direction is defined as x to -y rotation applied after up-down flip
		Scott said this should be zero when FRAME_ROTATE is defined as zero in DE MicroManager.
		'''
		return FRAME_ROTATE

	def custom_setup(self):
		'''DE64 Integration specific camera setting'''
		self.setElectronCounting('Disable')
		binvalue = self.getDEConfig(self.name, 'binning')
		self.setHardwareBinning(binvalue)
		self.setSensorHardwareBinning('Disable')
		self.setECApplyCountingGain('Disable')
		self.setProperty('Electron Counting - Dose Fractionation Number of Frames', 1)



class DE64c(DD):
	name = 'DE64c'
	model_name = 'DE64'

	def getPixelSize(self):
		psize = 6.5e-6
		return {'x': psize, 'y': psize}

	def getSystemGainDarkCorrected(self):
		return True

	def custom_setup(self):
		'''DE64 Counting specific camera setting'''
		self.setSensorHardwareBinning('Enable')
		self.countingSetUp()
		self.setCalculatedFractionNumber()

	def getSaveRawFrames(self):
		'''Save or Discard'''
		value = self.getProperty('Autosave Movie')
		if value == 'Save':
			return True
		elif value == 'Discard':
			return False
		else:
			raise ValueError('unexpected value from Autosave Raw Frames: %s' % (value,))

	def setSaveRawFrames(self, value):
		'''DE64 True: save frames,  False: discard frames'''
		if value:
			value_string = 'Save'
		else:
			value_string = 'Discard'
		self.setProperty('Autosave Movie', value_string)
