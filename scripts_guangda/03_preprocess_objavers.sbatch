#!/bin/bash
#SBATCH --job-name=preprocess_partverse
#SBATCH --output=preprocess_partverse_%j.out
#SBATCH --error=preprocess_partverse_%j.err
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
module load StdEnv/2023 apptainer/1.3.5 cuda/12.9

# [关键-1] 禁止 --nv 注入图形库，只保留 compute/utility
export NVIDIA_DRIVER_CAPABILITIES=compute,utility

run_once () {
  local IN_HOST="$1"
  local OUT_HOST="$2"

  apptainer exec --nv \
    --bind "${REPO_HOST}:${REPO_MNT}:ro" \
    --bind "${IN_HOST}:/mnt/input:ro" \
    --bind "${OUT_HOST}:/mnt/output" \
    --pwd "${REPO_MNT}" \
    \
    # [关键-2] 强制 PyOpenGL 用 EGL，避免 GLX
    --env PYOPENGL_PLATFORM=egl \
    --env EGL_PLATFORM=surfaceless \
    --env MPLBACKEND=Agg \
    \
    # [关键-3] 让动态链接优先搜容器内的 libGL，而不是 /.singularity.d/libs
    --env LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu:/miniconda3/lib:${LD_LIBRARY_PATH:-}" \
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
