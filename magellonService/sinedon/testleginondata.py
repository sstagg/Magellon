#!/usr/bin/env python

import leginondata

def queryTest():
	lq=leginondata.AcquisitionImageData()
	sq=leginondata.SessionData()
	pq=leginondata.PresetData()

	sq['name']='22feb18a'   #the value should be the name of a session at your site
	pq['name']='ex'   #the value should be the name of a preset associated with the session above
	lq['session']=sq  #setting the values so that sinedon can join across tables
	lq['preset']=pq
	imagedata=lq.query()   #performs the query and returns all the associated metadata to 

	print ('QUERY RESULTS')
	print ('filename', imagedata[0]['filename'])   #filename for the first ex image
	print ('name of the camera', imagedata[0]['camera']['ccdcamera']['name'])    #returns the name of the camera that took the image
	
if __name__ == '__main__':
	queryTest()
