#!/usr/bin/env python

import scipy
import numpy
from pyami import mrc, imagefun
import random

proj=mrc.read('proj.mrc')
stats=imagefun.edgeStats(proj)
for n in range(100):
	#generate shift
	shift=(random.randint(-20,20),random.randint(-20,20))
	
	#shift image. Notice "wrap" as the mode. That wraps the image around the edges
	shifted=scipy.ndimage.shift(proj,shift,mode='wrap')
	
	#add noise
	noised=shifted+numpy.random.normal(loc=stats['mean'],scale=3,size=proj.shape)
	name=('raw%02d.mrc' % (n))
	mrc.write(noised,name)
