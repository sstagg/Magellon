import numpy
import mrcfile as mrc
import cv2

def calc_mass(avg=None, apix=None, scalefactor=1, usebackground=False):
    particlemask, backgroundmask = make_masks_by_statistics(nstd=3, img=avg)
    backgroundmean = numpy.average(avg[backgroundmask])

    if usebackground is True:
        avg = avg - backgroundmean
    else:
        mean, std = get_edge_stats_for_box(avg, 3)
        avg = avg - mean
    pixsum = numpy.sum(avg[particlemask])
    angsum = pixsum * apix ** 2
    estmass = angsum * scalefactor
    return estmass

def make_masks_by_statistics(nstd=3, img=None):
    mean, std = get_edge_stats_for_box(img, 3) # use stats for 3 pixels inside edge to avoid edge effects
    particlemask = img > (mean + std * nstd)
    backgroundmask = numpy.invert(particlemask)
    return particlemask, backgroundmask

def get_edge_stats_for_box(img, clippix):
    edgepix = img[clippix:-clippix, clippix]
    edgepix = numpy.append(edgepix, img[clippix:-clippix, -clippix])
    edgepix = numpy.append(edgepix, img[clippix, clippix:-clippix])
    edgepix = numpy.append(edgepix, img[-clippix, clippix:-clippix])
    mean = edgepix.mean()
    std = edgepix.std()
    return mean, std

def sum_pixels_inside_boolmask(boolmask=None, img=None):
    boolarray = img > (mean + std * nstd)
    notboolarray = numpy.invert(boolarray)
    notptclmean = numpy.average(img[notboolarray])
    #img = img - notptclmean
    img = img - mean
    # scaled=img/(mean+std*nstd)
    # img = img/(mean+std*nstd)
    pixelsum = numpy.sum(img[boolmask])
    return pixelsum




def mask_otsu_thresholding(image):
    """
    Perform Otsu Thresholding.

    Returns:
        bool mask
    """
    # Convert the floating-point image to a suitable format (e.g., 8-bit)
    normalized_image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX, cv2.CV_8U)

    # Perform light Gaussian filter
    filtered = cv2.GaussianBlur(normalized_image, (5,5),0 )
    mrc.write('filtered.mrc', filtered, overwrite=True)

    # Apply Otsu's thresholding on the converted image
    threshvalue, thresholded = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    boolarray = thresholded > 0
    notboolarray = numpy.invert(boolarray)

    mean, std = getEdgeStatsForBox(image,3)
    image[notboolarray]=mean


