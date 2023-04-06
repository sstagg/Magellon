# import cupy as cp
# import mrcfile


class ImageFFTService:

    def compute_fft(self, input_filename, output_filename):
        print("computing fft")

    # def compute_fft(self, input_filename, output_filename):
    #     # Load the MRC image file onto the GPU
    #     with mrcfile.open(input_filename, mode='r', permissive=True) as mrc:
    #         data = cp.array(mrc.data)
    #
    #     # Compute the FFT of the image on the GPU
    #     fft = cp.fft.fftshift(cp.fft.fftn(data))
    #
    #     # Save the FFT image to a new MRC file
    #     with mrcfile.new(output_filename, overwrite=True) as mrc:
    #         mrc.set_data(cp.asnumpy(fft).astype(cp.float64))
