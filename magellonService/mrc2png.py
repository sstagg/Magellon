''' Converting one mrc file to png. '''

import mrcfile
import glob
import numpy as np
import argparse
from PIL import Image
import scipy.fftpack
import matplotlib.pyplot as plt

def setupParserOptions():
	ap = argparse.ArgumentParser()
	ap.add_argument('-i', '--indir', help="Provide path to input mrc file(s) directory")
	ap.add_argument('-o', '--outdir', help='Provide path to output directory')
	ap.add_argument('--height', type=int, default=1024,
			help='Height of the converted png in px. Default is 1024.')
	ap.add_argument('--thumbnailheight', type=int, default=494,
			help='Thumbnail Height of the converted png in px. Default is 494.')
	args = vars(ap.parse_args())
	return args

def save_fft(img, png_name, height=1024):
	png_out_dir = args['outdir']
	
	# Fourier transform of the image
	F1 = scipy.fftpack.fft2(img)
	# Shift so that low spatial frequencies are in the center.
	F2 = scipy.fft.fftshift(F1)
	
	newImg = np.log(1+abs(F2))

	f = downsample(newImg, height)
	newImg = Image.fromarray(abs(f))

	plt.imsave(png_out_dir + 'FFTs/' + png_name, newImg, cmap='gray')
	return

def downsample(img, height):
	'''
	Downsample 2d array using fourier transform.
	factor is the downsample factor.
	'''
	m,n = img.shape[-2:]
	ds_factor = m/height
	width = round(n/ds_factor/2)*2
	F = np.fft.rfft2(img)
	A = F[...,0:height//2,0:width//2+1]
	B = F[...,-height//2:,0:width//2+1]
	F = np.concatenate([A, B], axis=0)
	f = np.fft.irfft2(F, s=(height, width))   
	return f

def scale_image(img, height):
	newImg = downsample(img, height)
	newImg = ((newImg - newImg.min()) / ((newImg.max() - newImg.min()) + 1e-7) * 255)
	newImg = Image.fromarray(newImg).convert('L')
	newImg.rotate(180)
	return newImg

def mrc2png(args):
	mrc_in_dir = args['indir']
	png_out_dir = args['outdir']

	for filename in glob.iglob(mrc_in_dir + '*.mrc', recursive=True):
		try:
			print("filename " + filename)
			mic = mrcfile.open(filename, permissive=True).data
			mic = mic.reshape((mic.shape[-2], mic.shape[-1]))

			png_path = filename.split(".")[0] + ".png"
			thumnail_path = filename.split(".")[0] + "_TIMG.png"

			png_name = png_path.rsplit("/", 1)[1]
			thumbnail_name = thumnail_path.rsplit("/", 1)[1]

			newImg = scale_image(mic, args['height'])
			newTIMG = scale_image(mic, args['thumbnailheight'])
			
			save_fft(mic, png_name)

			newImg.save(png_out_dir + 'images/' + png_name)
			newTIMG.save(png_out_dir + 'thumbnails/' + thumbnail_name)
		except ValueError:
			print('An error occured when trying to save png ', filename)
			pass

if __name__ == '__main__':
	args = setupParserOptions()
	mrc2png(args)
