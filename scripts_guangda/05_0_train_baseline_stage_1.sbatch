#!/bin/bash
#SBATCH --job-name=baseline_training
#SBATCH --output=outlog_%j.out
#SBATCH --error=errlog_%j.out
#SBATCH --gpus-per-node=h100:4
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=256G
#SBATCH --time=96:00:00



REPO_HOST="/home/quanta/PartCrafter"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
DATASET_REPO="/scratch/quanta"


module --force purge
module load StdEnv apptainer cuda/12.9

apptainer exec --nv \
  --bind ${DATASET_REPO}/partcrafter_test_dataset:/dataset \
  ${SIF_IMG} \
  bash <<'BASH'
set -eo pipefail

CONDA_ENV_NAME="partcrafter"

export PATH=/miniconda3/bin:$PATH
eval "$(conda shell.bash hook)"
conda activate ${CONDA_ENV_NAME}
conda deactivate

conda activate ${CONDA_ENV_NAME}
conda_home="$(conda info | grep "active env location : " | cut -d ":" -f2-)"
conda_home="${conda_home#"${conda_home%%[![:space:]]*}"}"

export PYTHONPATH=${REPO_MNT}:${PYTHONPATH:-}
export CUDA_HOST_COMPILER="$conda_home/bin/gcc"
export CUDA_PATH="$conda_home"
export CUDA_HOME=$CUDA_PATH
export PATH="$CUDA_HOME/bin:$PATH"
export LD_LIBRARY_PATH="$CUDA_HOME/lib64:$LD_LIBRARY_PATH"
export PYOPENGL_PLATFORM=osmesa
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

command -v nvcc
command -v pip
command -v python


bash scripts/train_partcrafter.sh --config scripts_guangda/04_3_train_baseline_stage1_mp8_nt512.yaml --use_ema \
  --gradient_accumulation_steps 4 \
  --output_dir output_partcrafter \
  --max_val_steps 0 \
  --tag baseline_scaleup_mp8_nt512
BASH
