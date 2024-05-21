import numpy
import mrcfile as mrc
import cv2

def getEdgeStatsForBox(img, clippix):
    edgepix = img[clippix:-clippix, clippix]
    edgepix = numpy.append(edgepix, img[clippix:-clippix, -clippix])
    edgepix = numpy.append(edgepix, img[clippix, clippix:-clippix])
    edgepix = numpy.append(edgepix, img[-clippix, clippix:-clippix])
    mean = edgepix.mean()
    std = edgepix.std()
    return mean, std


def sumPixelsAboveThreshold(mean=None, std=None, nstd=3, img=None):
    boolarray = img > (mean + std * nstd)
    notboolarray = numpy.invert(boolarray)
    notptclmean = numpy.average(img[notboolarray])
    #img = img - notptclmean
    img = img - mean
    # scaled=img/(mean+std*nstd)
    # img = img/(mean+std*nstd)
    pixelsum = numpy.sum(img[boolarray])
    # pixelsum=numpy.sum(scaled[boolarray])
    return pixelsum

def calcMass(avg=None, apix=None, scalefactor=1, border=20):
    mean, std = getEdgeStatsForBox(avg, border)
    pixsum = sumPixelsAboveThreshold(mean=mean, std=std, img=avg)
    angsum = pixsum * apix ** 2
    estmass = angsum * scalefactor
    return estmass

# def maskAvgByStatistics(mean=None, std=None, nstd=3, img=None):
#      masks a copy of the image
#      masked=numpy.copy(img)
#      boolarray = masked > (mean + std * nstd)
#      notboolarray = numpy.invert(notboolarray)
#      edgemean, edgestd = getEdgeStatsForBox(masked, 3)
#      masked[notboolarray]=edgemean
#      return masked

def maskAvgByStatistics(nstd=3, img=None):
    # actually modifies the numpy array
     mean, std = getEdgeStatsForBox(img, 3)
     print(mean,std)
     boolarray = img > (mean + std * nstd)
     notboolarray = numpy.invert(boolarray)
     img[notboolarray]=mean


def mask_otsu_thresholding(image):
    """
    Perform Otsu Thresholding.

    Returns:
        masked image
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


