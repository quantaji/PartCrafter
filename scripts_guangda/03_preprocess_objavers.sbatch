#!/bin/bash
#SBATCH --job-name=preprocess_partverse
#SBATCH --output=outlog_%j.out
#SBATCH --error=errlog_%j.err
#SBATCH --gpus=nvidia_h100_80gb_hbm3_2g.20gb:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=1:00:00

set -euo pipefail

# --- 路径 ---
REPO_HOST="/home/quanta/PartCrafter"
REPO_MNT="/workspace"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"

INPUT1_HOST="/scratch/quanta/objaverse_selected"
OUTPUT1_HOST="/scratch/quanta/objaverse_partpacker_preprocessed"
INPUT2_HOST="/scratch/quanta/partverse_selected"
OUTPUT2_HOST="/scratch/quanta/partverse_partpacker_preprocessed"

mkdir -p "$OUTPUT1_HOST" "$OUTPUT2_HOST"

module --force purge
module load StdEnv apptainer cuda/12.9

export NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,display,video

run_once () {
  local IN_HOST="$1"
  local OUT_HOST="$2"

  apptainer exec --nv --cleanenv \
    --bind "${REPO_HOST}:${REPO_MNT}" \
    --bind "${IN_HOST}:/mnt/input" \
    --bind "${OUT_HOST}:/mnt/output" \
    --pwd "${REPO_MNT}" \
    --env PYOPENGL_PLATFORM=egl \
    --env EGL_PLATFORM=surfaceless \
    --env __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json \
    --env LD_LIBRARY_PATH='/.singularity.d/libs:/usr/lib/x86_64-linux-gnu' \
    "$SIF_IMG" \
    bash -lc "
      set -eo pipefail
      export PATH=${CONDA_ROOT}/bin:\$PATH
      eval \"\$(conda shell.bash hook)\"
      conda activate ${CONDA_ENV_NAME}
      export PYTHONPATH=${REPO_MNT}:\${PYTHONPATH:-}

      python -m datasets.preprocess.preprocess \
        --input /mnt/input \
        --output /mnt/output
    "
}

# 第一批
run_once "$INPUT1_HOST" "$OUTPUT1_HOST"
# 第二批
run_once "$INPUT2_HOST" "$OUTPUT2_HOST"
