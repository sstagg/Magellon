import mrcfile
import glob
import numpy as np
from PIL import Image
import scipy.fftpack
import matplotlib.pyplot as plt


class MrcImageService:
    # def __init__(self, indir, outdir, height=1024, thumbnailheight=494):
    #     self.indir = indir
    #     self.outdir = outdir
    #     self.height = height
    #     self.thumbnailheight = thumbnailheight

    def save_fft(self, img, out_dir, png_name, height=1024):
        # Fourier transform of the image
        F1 = scipy.fftpack.fft2(img)
        # Shift so that low spatial frequencies are in the center.
        F2 = scipy.fft.fftshift(F1)

        newImg = np.log(1 + abs(F2))

        f = self.down_sample(newImg, height)
        newImg = Image.fromarray(abs(f))

        plt.imsave(out_dir + png_name, newImg, cmap='gray')
        return

    def down_sample(self, img, height):
        '''
        Downsample 2d array using fourier transform.
        factor is the downsample factor.
        '''
        m, n = img.shape[-2:]
        ds_factor = m / height
        width = round(n / ds_factor / 2) * 2
        F = np.fft.rfft2(img)
        A = F[..., 0:height // 2, 0:width // 2 + 1]
        B = F[..., -height // 2:, 0:width // 2 + 1]
        F = np.concatenate([A, B], axis=0)
        f = np.fft.irfft2(F, s=(height, width))
        return f

    def scale_image(self, img, height):
        new_image = self.down_sample(img, height)
        new_image = ((new_image - new_image.min()) / ((new_image.max() - new_image.min()) + 1e-7) * 255)
        new_image = Image.fromarray(new_image).convert('L')
        new_image.rotate(180)
        return new_image

    def mrc2png(self, indir, outdir, height=1024, thumbnailheight=494):
        x=5
        for filename in glob.iglob(indir + '*.mrc', recursive=True):
            try:
                print("filename " + filename)
                mic = mrcfile.open(filename, permissive=True).data
                mic = mic.reshape((mic.shape[-2], mic.shape[-1]))

                png_path = filename.split(".")[0] + ".png"
                thumnail_path = filename.split(".")[0] + "_TIMG.png"

                png_name = png_path.rsplit("/", 1)[1]
                thumbnail_name = thumnail_path.rsplit("/", 1)[1]

                newImg = self.scale_image(mic, height)
                newTIMG = self.scale_image(mic, thumbnailheight)

                self.save_fft(mic, png_name)

                newImg.save(outdir + 'images/' + png_name)
                newTIMG.save(outdir + 'thumbnails/' + thumbnail_name)
            except ValueError:
                print('An error occured when trying to save png ', filename)
                pass
