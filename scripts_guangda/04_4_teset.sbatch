#!/bin/bash
#SBATCH --job-name=test_training
#SBATCH --output=outlog_%j.out
#SBATCH --error=errlog_%j.out
#SBATCH --gpus=nvidia_h100_80gb_hbm3_3g.40gb:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=1:00:00



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


bash scripts/train_partcrafter.sh --config scripts_guangda/04_1_train_cc_test.yaml --use_ema \
  --gradient_accumulation_steps 4 \
  --output_dir output_partcrafter \
  --max_val_steps 0 \
  --tag scaleup_mp8_nt512
BASH
