import os
from pyami import mrc
from appionlib import basicScript
from appionlib import apDisplay
from appionlib.apCtf import ctfdisplay

def run_ctf_evaluation(imagefile, apix, cs, kv, reslimit=5.0, defocus1=None, defocus2=None,
                       ampcontrast=None, extraphaseshift=None, astigangle=None, debug=False):
    imgdata = {
        'filename': os.path.abspath(imagefile),
        'image': mrc.read(imagefile),
    }
    if not os.path.isfile(imagefile):
        apDisplay.printError("Could not read micrograph for processing")

    if kv > 400.0 or kv < 60:
        apDisplay.printError("atypical high tension value %.1f kiloVolts"%(kv))	

    if cs > 7.0 or cs < 0.4:
        apDisplay.printError("atypical C_s value %.1f mm"%(cs))

    if apix > 20.0 or apix < 0.1:
        apDisplay.printError("atypical pixel size value %.1f Angstroms"%(apix))

    if defocus1 > 15.0 or defocus1 < 0.1:
        apDisplay.printError("atypical defocus #1 value %.1f microns (underfocus is positve)"%(defocus1))

    if defocus2 > 15.0 or defocus2 < 0.1:
        apDisplay.printError("atypical defocus #2 value %.1f microns (underfocus is positve)"%(defocus2))

    if abs(astigangle) > 0.01 and abs(astigangle) < 3.0:
        apDisplay.printWarning("atypical angle astigmatism value %.3f"%(astigangle))

    if ampcontrast < 0.0 or ampcontrast > 0.5:
        apDisplay.printError("atypical amplitude contrast value %.3f"%(ampcontrast))
    
    if not extraphaseshift:
        apDisplay.printError("could not read extra phase shift value")
   
    ctfdata = {
        'volts': float(kv)* 1e3,
        'cs': float(cs),
        'apix': float(apix),
        'defocus1': float(defocus1) * 1e-6 if defocus1 is not None else None,
        'defocus2': float(defocus2) * 1e-6 if defocus2 is not None else None,
        'angle_astigmatism': float(astigangle),
        'amplitude_contrast': float(ampcontrast),
        "extra_phase_shift": float(extraphaseshift)
    }
    
    for i in ctfdata:
        print(type(i))
    a = ctfdisplay.CtfDisplay()
    a.debug = debug
    ctfdisplay.ctftools.debug = debug
    ctfdisplaydict = a.CTFpowerspec(imgdata, ctfdata, None, None, True)
    if ctfdisplaydict is None:
        raise ValueError("CTF powerspec calculation failed")

    ctfdata['confidence_30_10'] = ctfdisplaydict['conf3010']
    ctfdata['confidence_5_peak'] = ctfdisplaydict['conf5peak']
    ctfdata['overfocus_conf_30_10'] = ctfdisplaydict['overconf3010']
    ctfdata['overfocus_conf_5_peak'] = ctfdisplaydict['overconf5peak']
    ctfdata['resolution_80_percent'] = ctfdisplaydict['res80']
    ctfdata['resolution_50_percent'] = ctfdisplaydict['res50']
    ctfdata['confidence'] = max(ctfdisplaydict['conf5peak'], ctfdisplaydict['conf3010'])

    return ctfdata
