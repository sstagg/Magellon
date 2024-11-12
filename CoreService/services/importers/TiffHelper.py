from tifffile import TiffFile
from PIL import Image
import numpy as np
import xml.etree.ElementTree as ET


# Constants
SCOPE_DICT = {
    "3593": ["Krios", 2.7]  # Example scope dict entry, modify as needed
}

DEBUG = False

# TIFF tag definitions
tif_tags = {
    256: "ImageWidth",
    257: "ImageLength",
    258: "BitsPerSample",
    259: "Compression",
    262: "PhotometricInterpretation",
    270: "ImageDescription",
    273: "StripOffsets",
    277: "SamplesPerPixel",
    278: "RowsPerStrip",
    279: "StripByteCounts",
    282: "XResolution",
    283: "YResolution",
    284: "PlanarConfiguration",
    296: "ResolutionUnit",
    306: "DateTime",
    339: "SampleFormat",
    340: "MinSampleValue",
    341: "MaxSampleValue",
    65001: "TFS EER Metadata",
    65100: "TFS EER gain Metadata",
}

def _standardize_dict(acq_dict):
    """Convert values to expected format."""
    std_dict = {
        'MicroscopeID': "3593",
        'Detector': 'EF-CCD',
        'Mode': 'Counting',
        'NumSubFrames': acq_dict['nimg'],
        'ExposureTime': acq_dict['ExposureTime'],
        'Dose': 0,
        'OpticalGroup': 'opticsGroup1',
        'PhasePlateUsed': 'false',
        'MTF': 'None',
        'Voltage': 300,
        'Binning': 1,
        'Warning': 'TIF header does not contain enough metadata, please check these values!'
    }

    desc = acq_dict['ImageDescription'].split("\n")
    std_dict['GainReferenceTransform'] = desc[0].split("r/f")[-1]
    std_dict['GainReference'] = desc[1].strip() or None

    if len(desc) == 3:
        std_dict['DefectFile'] = desc[2].strip()

    # Find mode/detector from image size
    sr = 1.0
    if acq_dict['ImageLength'] in [7676, 11520]:
        sr = 2.0
        std_dict['Mode'] = 'Super-resolution'
    elif acq_dict['ImageLength'] == acq_dict['ImageWidth'] == 4096:
        std_dict['Detector'] = 'BM-Falcon'

    # Find pixel size A/px
    if acq_dict['ResolutionUnit'] == 1:  # unknown
        std_dict['PixelSpacing'] = 1.0
    elif acq_dict['ResolutionUnit'] == 2:  # inch
        std_dict['PixelSpacing'] = float(acq_dict['XResolution'][0]) / 2.54e+8 / sr
    else:  # cm
        std_dict['PixelSpacing'] = float(acq_dict['XResolution'][0]) / 1e+8 / sr

    if 'Dose_e/px' in acq_dict:
        std_dict['Dose'] = acq_dict['Dose_e/px'] / (float(std_dict['PixelSpacing'])) ** 2  # e/A^2

    std_dict['Cs'] = SCOPE_DICT[std_dict['MicroscopeID']][1]

    # Convert all to str
    for key in std_dict:
        std_dict[key] = str(std_dict[key])

    return std_dict

def parse_tif(file_path):
    """Parse TIFF file and extract metadata."""
    acq_dict = {
        "ImageDescription": "None\n",
        "DateTime": "None",
        "XResolution": (1, 1),
        "ResolutionUnit": 1,
        "ExposureTime": 1.0
    }

    with TiffFile(file_path) as tif:
        for page in tif.pages:
            for tag in page.tags:
                if tag.code in tif_tags:
                    acq_dict[tif_tags[tag.code]] = tag.value
            break

        acq_dict["nimg"] = len(tif.pages)

    if 'TFS EER Metadata' in acq_dict:
        root = ET.fromstring(acq_dict["TFS EER Metadata"].decode('utf-8'))
        tmp = {}
        for item in root:
            tmp[item.get('name')] = item.text

        acq_dict['ExposureTime'] = float(tmp['exposureTime'])
        acq_dict['Dose_e/px'] = float(tmp['totalDose'])

    return _standardize_dict(acq_dict)




def convert_tiff_to_image(tiff_path, output_path, output_type='jpeg', quality=95, size_ratio=1.0):
    """
    Convert a TIFF file to either JPEG or PNG format, with options for quality and size ratio.

    Parameters:
        tiff_path (str): Path to the input TIFF file.
        output_path (str): Path to the output file.
        output_type (str): 'jpeg' or 'png' to specify the output format.
        quality (int, optional): JPEG quality, from 0 (worst) to 100 (best). Defaults to 95.
        size_ratio (float, optional): Ratio to resize the image. Defaults to 1.0 (no resize).

    Returns:
        str: The path to the saved output file.
    """
    # Validate output type
    if output_type.lower() not in ['jpeg', 'png']:
        raise ValueError("Output type must be 'jpeg' or 'png'")

    # Open the TIFF file
    with TiffFile(tiff_path) as tiff:
        image = tiff.asarray()

    # Convert 16-bit images to 8-bit
    if image.dtype == np.uint16:
        image = ((image - image.min()) * (255.0 / (image.max() - image.min()))).astype(np.uint8)

    # Convert to PIL Image
    pil_image = Image.fromarray(image)

    # Resize if size_ratio is specified
    if size_ratio != 1.0:
        new_size = (int(pil_image.width * size_ratio), int(pil_image.height * size_ratio))
        pil_image = pil_image.resize(new_size, resample= Image.Resampling.LANCZOS)

    # Save image in the specified format
    save_params = {'quality': quality} if output_type.lower() == 'jpeg' else {}
    pil_image.save(output_path, output_type.upper(), **save_params)

    return output_path


def convert_tiff_to_jpeg(tiff_path, jpeg_path):
    """
     Convert TIFF to JPEG with appropriate handling for EPU TIFF files.
     Returns the path to the saved JPEG file.
     """
    with TiffFile(tiff_path) as tiff:
        # Get the first image from the TIFF file
        image = tiff.asarray()

        # Handle 16-bit images
        if image.dtype == np.uint16:
            # Scale to 8-bit
            image = ((image - image.min()) * (255.0 / (image.max() - image.min()))).astype(np.uint8)

        # Convert to PIL Image
        pil_image = Image.fromarray(image)

        # Save as JPEG with high quality
        pil_image.save(jpeg_path, 'JPEG', quality=95)

        return jpeg_path



def convert_tiff_to_png(tiff_path, png_path):
    """
    Convert TIFF to PNG with appropriate handling for EPU TIFF files.
    Returns the path to the saved PNG file.
    """
    with TiffFile(tiff_path) as tiff:
        # Get the first image from the TIFF file
        image = tiff.asarray()

        # Handle 16-bit images
        if image.dtype == np.uint16:
            # Scale to 8-bit
            image = ((image - image.min()) * (255.0 / (image.max() - image.min()))).astype(np.uint8)

        # Convert to PIL Image
        pil_image = Image.fromarray(image)

        # Save as PNG
        pil_image.save(png_path, 'PNG')

        return png_path


