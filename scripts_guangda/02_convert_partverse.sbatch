#!/bin/bash
#SBATCH --job-name=merge_partverse
#SBATCH --output=merge_partverse_%j.out
#SBATCH --error=merge_partverse_%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=128G
#SBATCH --time=24:00:00

set -euo pipefail

module load apptainer/1.3.5

# Host paths
SRC_DIR_HOST="/scratch/wingli/partverse/textured_part_glbs"
TGT_DIR_HOST="/scratch/quanta/partverse_selected"
ID_JSON_HOST="/home/quanta/PartCrafter/notebooks/partverse_selected.json"
PY_SCRIPT_HOST="/home/quanta/PartCrafter/scripts_guangda/01_convert_partverse.py"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"

CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"

# make sure output dir exists on host
mkdir -p "$TGT_DIR_HOST"

# try to load apptainer module if cluster uses environment modules
module load apptainer 2>/dev/null || true

apptainer exec \
  --bind "${SRC_DIR_HOST}:/mnt/src" \
  --bind "${TGT_DIR_HOST}:/mnt/out" \
  --bind "/home/quanta:/home/quanta" \
  "$SIF_IMG" \
  bash -lc "
    set -eo pipefail

    export PATH=${CONDA_ROOT}/bin:\$PATH
    eval \"\$(conda shell.bash hook)\"
    conda activate ${CONDA_ENV_NAME}

    python ${PY_SCRIPT_HOST} \
      --json ${ID_JSON_HOST} \
      --srcdir /mnt/src \
      --tgtdir /mnt/out
  "






