#!/usr/bin/env python3
import glob 
import shutil 
import linecache
import os,sys
import optparse
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use('TkAgg')
from matplotlib import pyplot as plt
from train import MRCNetwork, Sequences
from predict import DatasetPredictor, CryosparcPredictor, RelionPredictor
from dataset import MRCImageDataset
from util import unconvert_labels

#===============
def setupParserOptions():
	parser = optparse.OptionParser()
	parser.set_description("Assess cryoSPARC 2D class averages")
	parser.set_usage("%prog -i <cryoSPARC job dir> -w <weights file>")
	parser.add_option("-i", "--input", type="string", metavar="DIRECTORY",
	    help="cryoSPARC job directory")
	parser.add_option("-o", "--output", type="string", metavar="DIRECTORY",
            help="Output directory")
	parser.add_option("-w", "--weights", type="string", metavar="FILE",
	    help="Pre-trained neural network weights file (e.g., final_model_cont.pth)")
	options,args = parser.parse_args()
	if len(args) > 0:
		parser.error("Unknown commandline options: " +str(args))
	if len(sys.argv) < 2:
		parser.print_help()
		parser.error("No options defined")
	params = {}
	for i in parser.option_list:
		if isinstance(i.dest, str):
			params[i.dest] = getattr(options, i.dest)
	return params

def checkConflicts(params):
	if not os.path.exists(params['input']):
		print("Error: Path does not exist %s" %(params['input']))
		sys.exit()
	if not os.path.exists(params['weights']):
		print("Error: Path does not exist %s" %(params['weights']))
		sys.exit()
	if os.path.exists(params['output']):
		print("Error: Output directory %s already exists. Exiting." %(params['output']))
		sys.exit()

def cryosparcpredict(params):
    job_dir = params['input']
    feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
    num_features = 6
    use_features = (num_features > 0)
    fixed_len = 210

    model = MRCNetwork(None, Sequences.sequence8, num_features)
    save_path = params['weights']
    predictor = CryosparcPredictor(model, save_path, device='cpu')

    pred = predictor.predict_single(job_dir, feature_scale=feature_scale, fixed_len=fixed_len)

    #Make output directory & put info file
    os.mkdir(params['output'])
    o1=open('%s/info.txt' %(params['output']),'w')
    o1.write('Input cryoSPARC directory: %s' %(params['input']))
    o1.close()

    #Get class average name
    mrclist=glob.glob('%s/*.mrc' %(params['input']))
    if len(mrclist)>1:
        print("Error: found more than one .mrc stack in %s. Exiting" %(params['input']))
        sys.exit()
    shutil.copyfile(mrclist[0],'%s/%s_classes.mrcs' %(params['output'],mrclist[0].split('/')[-1][:-4]))

    scriptdir=__file__.split('/')
    del scriptdir[-1]
    scriptdir='/'.join(scriptdir)
    shutil.copyfile('%s/dummy_star_4_display.star' %(scriptdir),'%s/%s_data.star' %(params['output'],mrclist[0].split('/')[-1][:-4]))

    o1=open('%s/%s_model.star' %(params['output'],mrclist[0].split('/')[-1][:-4]),'w')
    o1.write('''data_model_classes

loop_
_rlnReferenceImage #1
_rlnClassPriorOffsetY #2\n''')
    
    counter=0
    while counter < len(pred.tolist()):
        o1.write('%05i@%s/%s_classes.mrcs %.3f\n' %(counter+1,params['output'],mrclist[0].split('/')[-1][:-4],pred.tolist()[counter]))
        counter=counter+1
    o1.close()

if __name__ == '__main__':
    params = setupParserOptions()
    checkConflicts(params)
    cryosparcpredict(params)
