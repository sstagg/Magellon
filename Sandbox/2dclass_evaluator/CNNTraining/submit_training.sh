#!/bin/tcsh
### Job name
#SBATCH --job-name=Train_NN
#SBATCH --error=/nfs/home/khom/test_projects/CNNTraining/logs/final_model_cont.out
#SBATCH --output=/nfs/home/khom/test_projects/CNNTraining/logs/final_model_cont.out
##SBATCH --open-mode=append
### Queue name
#SBATCH --partition=cryosparc
### Specify the number of nodes and thread (ppn) for your job.
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:2
### Specify memory
#SBATCH --mem=24G
### Tell PBS the anticipated run-time for your job, where walltime=HH:MM:SS
#SBATCH --time=36:00:00
### Specify scratch
##SBATCH --gres=lscratch:8gb
#################################

# $1 is the path to the Python script to run

cd $SLURM_SUBMIT_DIR
module load cuda/11.3
module load relion/3.1-cuda
module load pytorch/1.11.1py38-cuda
python -u "$1"