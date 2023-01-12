#!/usr/bin/env python
# encoding: utf-8

import json
import glob
import io
import base64
from base64 import encodebytes, b64encode
from flask import Flask, jsonify, send_file, request
from PIL import Image
import mrc2png
from itertools import groupby
import numpy as np
import os
from lib import mgDatabase
from operator import itemgetter

app = Flask(__name__)

def get_response_image(image_path):
	pil_img = Image.open(image_path, mode='r') # reads the PIL image
	byte_arr = io.BytesIO()
	pil_img.save(byte_arr, format='PNG') # convert the PIL image to byte array
	encoded_img = b64encode(byte_arr.getvalue()).decode('ascii') # encode as base64
	return encoded_img

''' define a function for key '''
def key_func(k):
	return k['ext']

def format_data_by_ext(data):
	sortedRes = []
	response = []
	# sort data by 'ext' key.
	sortedRes = sorted(data, key=key_func)

	for key, value in groupby(sortedRes, key_func):
		item = {}
		imgGroupByExt = []
		item['ext'] = key

		for image in value:
				imgGroupByExt.append(image)

		sorted_imgGroupByExt = sorted(imgGroupByExt, key=itemgetter('name'), reverse=True)
		
		item['images'] = sorted_imgGroupByExt
		response.append(item)
	return response

@app.route('/get_image', methods=['GET'])
def get_image():
	response = send_file('images/1/22apr01a_b_00019gr_00001sq_v02_00019hl_00016ex_c-DW.mrc.png', mimetype='image/png') 
	response.headers.add('Access-Control-Allow-Origin', '*')
	return response

@app.route('/get_images',methods=['GET'])
def get_images():
	encoded_images = []
	data = []

	root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/thumbnails/"

	filename_list = os.listdir(root_dir)
	parent_file_ext = set()

	for filename in filename_list:
		if len(filename.split("_")) > 6:
			parent_file_ext.add(filename.split("_")[5])
		else:
			parent_file_ext.add('misc')

	stack_3_images_list = set()

	for ext in parent_file_ext:
		count = 0
		for filename in filename_list:
			if (ext in filename) and len(filename.split("_")) >= 6 and (filename.endswith(ext+'_TIMG.png')) and count == 0:
				stack_3_images_list.add(filename)
				count += 1

		for filename in filename_list:
			if (ext in filename) and not filename.endswith(ext+'_TIMG.png') and count < 3:
				#print("else 3 filenames - ", filename)
				stack_3_images_list.add(filename)
				count += 1

	for filename in glob.iglob(root_dir + '*.png', recursive=True):
		if(filename.rsplit("/", 1)[1] not in stack_3_images_list):
			continue
		item = {}
		shortName = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]   # get image name
		item['name'] = shortName
		item['encoded_image'] = get_response_image(filename)
		item['ext'] = shortName.split("_")[5] if len(shortName.split("_")) > 5 else "misc"
		data.append(item)

	res = format_data_by_ext(data)
	response = jsonify({'result': res})
	response.headers.add('Access-Control-Allow-Origin', '*')
	return response

@app.route('/get_image_by_thumbnail', methods=['GET'])
def get_image_by_thumbnail():
	args = request.args
	name = args.get('name')

	root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/images/"

	response = send_file(root_dir + name + '.png', mimetype='image/png') 
	response.headers.add('Access-Control-Allow-Origin', '*')
	return response

@app.route('/get_images_by_stack',methods=['GET'])
def get_images_by_stack():
	args = request.args
	ext = args.get('ext')

	encoded_images = []
	data = []
	''' path contains list of mrc thumbnails '''
	root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/thumbnails/"

	for filename in glob.iglob(root_dir + '*.png', recursive=True):
		item = {}
		shortName = (filename.rsplit("/", 1)[1]).rsplit(".", 1)[0]   # get image name
		item['name'] = shortName
		item['ext'] = shortName.split("_")[5] if len(shortName.split("_")) > 5 else "misc"
		if ext == item['ext']:
			item['encoded_image'] = get_response_image(filename)
			data.append(item)

	res = format_data_by_ext(data)
	response = jsonify({'result': res})
	response.headers.add('Access-Control-Allow-Origin', '*')
	return response

@app.route('/get_fft_image', methods=['GET'])
def get_fft_image():
	args = request.args
	name = args.get('name')

	root_dir = r"/Users/rupalimyskar/Downloads/Stagg Lab/mywork/code/magellonService/images/rawdata/FFTs/"

	response = send_file(root_dir + name + '.png', mimetype='image/png') 
	response.headers.add('Access-Control-Allow-Origin', '*')
	return response

@app.route('/get_image_data', methods=['GET'])
def get_image_data():
	args = request.args
	name = args.get('name')

	data = mgDatabase.getImageData(name)

	''' Get pixel size in Angstroms '''
	pixelsize = mgDatabase.getPixelSize(data)

	''' Get dose in electrons per Angstrom '''
	dose = mgDatabase.getDoseFromImageData(data)

	item = {}
	item['defocus'] = round(data['preset']['defocus'] * 1.e6, 2)
	item['mag'] = data['preset']['magnification']
	item['filename'] = data['filename']
	item['pixelsize'] = round(pixelsize, 3)

	if dose is not None:
		item['dose'] = round(dose, 2)
	else:
		item['dose'] = 'none'

	response = jsonify({'result': item})
	response.headers.add('Access-Control-Allow-Origin', '*')
	return response

app.run()
