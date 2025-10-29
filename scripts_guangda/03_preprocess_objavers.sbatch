#!/bin/bash
#SBATCH --job-name=preprocess_partverse
#SBATCH --output=preprocess_partverse_%j.out
#SBATCH --error=preprocess_partverse_%j.err
#SBATCH --gpus=nvidia_h100_80gb_hbm3_2g.20gb:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=24:00:00

set -euo pipefail

# host paths
INPUT_HOST="/scratch/quanta/objaverse_selected"
OUTPUT_HOST="/scratch/quanta/objaverse_partpacker_preprocessed"
WORKDIR_HOST="/home/quanta/PartCrafter"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"

CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"

# make sure output dir exists on host
mkdir -p "$OUTPUT_HOST"

# load apptainer module if available
module --force purge
module load StdEnv/2023 apptainer/1.3.5 cuda/12.9

# run container with gpu
apptainer exec \
  --nv \
  --bind "${INPUT_HOST}:/mnt/input" \
  --bind "${OUTPUT_HOST}:/mnt/output" \
  --bind "/home/quanta:/home/quanta" \
  "$SIF_IMG" \
  bash -lc "
    set -eo pipefail

    cd ${WORKDIR_HOST}

    export PATH=${CONDA_ROOT}/bin:\$PATH
    eval \"\$(conda shell.bash hook)\"
    conda activate ${CONDA_ENV_NAME}

    python datasets/preprocess/preprocess.py \
      --input /mnt/input \
      --output /mnt/output
  "

# second 
INPUT_HOST="/scratch/quanta/partverse_selected"
OUTPUT_HOST="/scratch/quanta/partverse_partpacker_preprocessed"
WORKDIR_HOST="/home/quanta/PartCrafter"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"

CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"

# make sure output dir exists on host
mkdir -p "$OUTPUT_HOST"

# load apptainer module if available
module load apptainer 2>/dev/null || true

# run container with gpu
apptainer exec \
  --nv \
  --bind "${INPUT_HOST}:/mnt/input" \
  --bind "${OUTPUT_HOST}:/mnt/output" \
  --bind "/home/quanta:/home/quanta" \
  "$SIF_IMG" \
  bash -lc "
    set -eo pipefail

    cd ${WORKDIR_HOST}

    export PATH=${CONDA_ROOT}/bin:\$PATH
    eval \"\$(conda shell.bash hook)\"
    conda activate ${CONDA_ENV_NAME}

    python datasets/preprocess/preprocess.py \
      --input /mnt/input \
      --output /mnt/output
  "
