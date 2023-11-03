#!/bin/tcsh
### Job name
#SBATCH --job-name=Train_Experiment_CNN_1
#SBATCH --error=/nfs/home/khom/test_projects/CNNTraining/logs/experiment_model_2.err
#SBATCH --output=/nfs/home/khom/test_projects/CNNTraining/logs/experiment_model_2.out
### Queue name
#SBATCH --partition=cryosparc
### Specify the number of nodes and thread (ppn) for your job.
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:2
### Specify memory
#SBATCH --mem=32G
### Tell PBS the anticipated run-time for your job, where walltime=HH:MM:SS
#SBATCH --time=24:00:00
### Specify scratch
##SBATCH --gres=lscratch:8gb
#################################
cd $SLURM_SUBMIT_DIR
module load relion/4.0b1-cuda
module load pytorch
module load tensorflow
python -u train.py