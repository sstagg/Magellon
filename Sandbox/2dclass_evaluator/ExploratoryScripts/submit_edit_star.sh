#!/bin/tcsh
### Job name
#SBATCH --job-name=Quantify_Metadata
#SBATCH --error=/nfs/home/khom/test_projects/ExploratoryScripts/outputs/logs/run_model.err
#SBATCH --output=/nfs/home/khom/test_projects/ExploratoryScripts/outputs/logs/run_model.out
### Queue name
#SBATCH --partition=cryosparc4
### Specify the number of nodes and thread (ppn) for your job.
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:0
### Specify memory
#SBATCH --mem-per-cpu=2gb
### Tell PBS the anticipated run-time for your job, where walltime=HH:MM:SS
#SBATCH --time=72:00:00
### Specify scratch
##SBATCH --gres=lscratch:8gb
#################################
cd $SLURM_SUBMIT_DIR
module load relion/4.0b1-cuda
module load pytorch
python edit_optimizer.py