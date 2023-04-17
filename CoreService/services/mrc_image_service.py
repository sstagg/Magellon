import mrcfile
import os
import numpy as np
import scipy
from PIL import Image
import matplotlib.pyplot as plt
from scipy.fft import fft2
import scipy.fftpack

from config import IMAGE_SUB_URL, THUMBNAILS_SUB_URL, FFT_SUB_URL


class MrcImageService:
    # def __init__(self, indir, outdir, height=1024, thumbnailheight=494):
    #     self.indir = indir
    #     self.outdir = outdir
    #     self.height = height
    #     self.thumbnailheight = thumbnailheight

    def create_image_directory(self, image_path):
        """
        Creates the directory for the given image path if it does not exist.

        Args:
        image_path (str): The absolute path of the image file.

        Returns:
        None
        """
        try:
            directory = os.path.dirname(image_path)
            if not os.path.exists(directory):
                os.makedirs(directory)
        except Exception as e:
            print(f"An error occurred while creating the directory: {str(e)}")

    def compute_dir_fft(self, in_dir, out_dir, height=1024):
        files = [os.path.abspath(os.path.join(in_dir, f)) for f in os.listdir(in_dir) if
                 os.path.isfile(os.path.join(in_dir, f))]
        fft_dir_path = os.path.join(out_dir, FFT_SUB_URL)
        self.create_image_directory(fft_dir_path)
        for abs_file_name in files:
            fft_file_path = os.path.join(fft_dir_path,
                                         os.path.splitext(os.path.basename(abs_file_name))[0] + "_FFT.png")
            with mrcfile.open(abs_file_name, permissive=True) as mrc:
                mic = mrc.data.reshape(mrc.data.shape[-2], mrc.data.shape[-1])
            self.compute_fft(img=mic, abs_out_file_name=fft_file_path, height=height)

    def compute_fft(self, img, abs_out_file_name, height=1024):
        # Fourier transform of the image
        F1 = fft2(np.array(img).astype(float))
        # Shift so that low spatial frequencies are in the center.
        F2 = scipy.fft.fftshift(F1)

        new_img = np.log(1 + abs(F2))

        f = self.down_sample(new_img, height)
        new_img = Image.fromarray(abs(f))

        plt.imsave(abs_out_file_name, new_img, cmap='gray')
        return

    def compute_file_fft(self, mrc_abs_path, abs_out_file_name, height=1024):
        # Fourier transform of the image
        with mrcfile.open(mrc_abs_path, permissive=True) as mrc:
            mic = mrc.data.reshape(mrc.data.shape[-2], mrc.data.shape[-1])
        F1 = fft2(np.array(mic).astype(float))
        # Shift so that low spatial frequencies are in the center.
        F2 = scipy.fft.fftshift(F1)

        new_img = np.log(1 + abs(F2))

        f = self.down_sample(new_img, height)
        new_img = Image.fromarray(abs(f))

        plt.imsave(abs_out_file_name, new_img, cmap='gray')
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

    def convert_mrc_dir_to_png(self, in_dir, out_dir, height=1024, thumbnail_height=494):
        """
            Convert all MRC files in the input directory to PNG format and save them in the output directory.
            Args:
                in_dir (str): Input directory path containing MRC files.
                out_dir (str): Output directory path to save the converted PNG files.
                height (int, optional): Height of the PNG image. Defaults to 1024.
                thumbnail_height (int, optional): Height of the thumbnail image. Defaults to 494.
            Returns:
                None
        """
        # files=glob.iglob(indir + '*.mrc', recursive=True)
        # files=glob.glob(indir + '*.mrc', recursive=True)
        # files = [f for f in os.listdir(indir) if os.path.isfile(os.path.join(indir, f))]
        files = [os.path.abspath(os.path.join(in_dir, f)) for f in os.listdir(in_dir) if
                 os.path.isfile(os.path.join(in_dir, f))]
        for filename in files:
            self.convert_mrc_to_png(filename, out_dir, height, thumbnail_height)

    def convert_mrc_to_png(self, abs_file_path, out_dir, height=1024, thumbnail_height=494):
        try:
            print(f"filename {abs_file_path}")
            with mrcfile.open(abs_file_path, permissive=True) as mrc:
                mic = mrc.data.reshape(mrc.data.shape[-2], mrc.data.shape[-1])

            png_path = os.path.join(out_dir, IMAGE_SUB_URL,
                                    os.path.splitext(os.path.basename(abs_file_path))[0] + ".png")
            thumbnail_path = os.path.join(out_dir, THUMBNAILS_SUB_URL,
                                          os.path.splitext(os.path.basename(abs_file_path))[0] + "_TIMG.png")

            self.create_image_directory(png_path)
            self.create_image_directory(thumbnail_path)

            # fft_path = os.path.join(out_dir, FFT_SUB_URL,
            #                         os.path.splitext(os.path.basename(abs_file_path))[0] + "_FFT.png")
            # self.create_image_directory(fft_path)
            # self.compute_fft(img=mic, abs_out_file_name=fft_path)

            new_image = self.scale_image(mic, height)
            new_image.save(png_path)

            new_timg = self.scale_image(mic, thumbnail_height)
            new_timg.save(thumbnail_path)

        except ValueError:
            print(f"An error occurred when trying to save png {abs_file_path}")

    # def convert_mrc_to_png(self, abs_file_path, outdir, height=1024, thumbnail_height=494):
    #     try:
    #         print("filename " + abs_file_path)
    #         mic = mrcfile.open(abs_file_path, permissive=True).data
    #         mic = mic.reshape((mic.shape[-2], mic.shape[-1]))
    #
    #         new_image = self.scale_image(mic, height)
    #         new_image.save(outdir + IMAGE_SUB_URL + os.path.basename(os.path.splitext(abs_file_path)[0] + ".png"))
    #
    #         new_timg = self.scale_image(mic, thumbnail_height)
    #         new_timg.save(outdir + THUMBNAILS_SUB_URL + os.path.basename(os.path.splitext(abs_file_path)[0] + "_TIMG.png"))
    #         # self.compute_fft(mic, png_name)
    #
    #     except ValueError:
    #         print('An error occured when trying to save png ', abs_file_path)
    #         pass
