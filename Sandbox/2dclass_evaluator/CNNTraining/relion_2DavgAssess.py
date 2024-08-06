#!/usr/bin/env python3
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
	parser.set_description("Assess RELION 2D class averages")
	parser.set_usage("%prog -i <RELION .mrcs avgs> -m <RELION model.star file>")
	parser.add_option("-i", "--input", type="string", metavar="FILE",
		help="RELION stack of class averages (.mrcs)")
	parser.add_option("-m", "--model", type="string", metavar="FILE",
		help="RELION model.star file associated with 2D averages")
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
	if not os.path.exists(params['model']):
		print("Error: Path does not exist %s" %(params['model']))
		sys.exit()
	if not os.path.exists(params['weights']):
		print("Error: Path does not exist %s" %(params['weights']))
		sys.exit()

def relion_prediction(params):
    mrcs_path = params['input']
    model_path = params['model']
    feature_scale = {'dmean_mass': 1e-8, 'dmedian_mass': 1e-8, 'dmode_mass': 1e-8}
    num_features = 6
    use_features = (num_features > 0)
    fixed_len = 210

    model = MRCNetwork(None, Sequences.sequence8, num_features)
    save_path = params['weights']
    predictor = RelionPredictor(model, save_path, device='cpu')

    pred = predictor.predict_single(mrcs_path, model_path, recover_labels=True,
                                    feature_scale=feature_scale, fixed_len=fixed_len)

    out='%s_magellon_model.star' %(params['model'][:-11])
    o1=open(out,'w')
    shutil.copyfile(params['input'],'%s_magellon_classes.mrcs' %(params['model'][:-11]))
    shutil.copyfile('%s_data.star' %(params['model'][:-11]),'%s_magellon_data.star' %(params['model'][:-11]))

    for line in open(params['model'],'r'):
        if '_rlnClassPriorOffsetY' in line:
            priorcolnum=int(line.split('#')[-1])

    counter=0
    while counter <len(open(params['model'],'r').readlines()):
        line=linecache.getline(params['model'],counter)
        #for line in open(params['model'],'r'):
        if 'data_model_class_1' in line:
            counter=10000
            #if '_rlnReferenceImage' in line:
            #    line=line.replace('_rlnReferenceImage','_rlnImageName')
        if len(line)==0:
            o1.write(line)
        if len(line)>0:
            if '.mrcs' in line:
                partnum=int(line.split('@')[0])
                l=line.split()
                l[priorcolnum-1]=str(pred.tolist()[partnum-1])
                line='\t'.join(l)
                o1.write('%s\n' %(line))
            if not '.mrcs' in line:
                o1.write(line)
        counter=counter+1
    o1.close()
        

if __name__ == '__main__':
    params = setupParserOptions()
    checkConflicts(params)
    relion_prediction(params)
