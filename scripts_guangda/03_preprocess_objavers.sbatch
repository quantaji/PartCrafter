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

# paths
REPO_HOST="/home/quanta/PartCrafter"
REPO_MNT="/workspace"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"

# run-1 IO
INPUT1_HOST="/scratch/quanta/objaverse_selected"
OUTPUT1_HOST="/scratch/quanta/objaverse_partpacker_preprocessed"

# run-2 IO
INPUT2_HOST="/scratch/quanta/partverse_selected"
OUTPUT2_HOST="/scratch/quanta/partverse_partpacker_preprocessed"

mkdir -p "$OUTPUT1_HOST" "$OUTPUT2_HOST"

module --force purge
module load StdEnv/2023 apptainer/1.3.5 cuda/12.9

run_once () {
  local IN_HOST="$1"
  local OUT_HOST="$2"

  apptainer exec \
    --nv \
    --bind "${REPO_HOST}:${REPO_MNT}:ro" \
    --bind "${IN_HOST}:/mnt/input:ro" \
    --bind "${OUT_HOST}:/mnt/output" \
    --pwd "${REPO_MNT}" \
    "$SIF_IMG" \
    bash -lc "
      set -eo pipefail
      export PATH=${CONDA_ROOT}/bin:\$PATH
      eval \"\$(conda shell.bash hook)\"
      conda activate ${CONDA_ENV_NAME}
      # 关键：让 'import src....' 可见
      export PYTHONPATH=${REPO_MNT}:\${PYTHONPATH:-}

      # 若仍失败，取消注释下一行查看 sys.path
      # python - <<'PY'; import sys, pprint; pprint.pprint(sys.path); PY

      python -m datasets.preprocess.preprocess \
        --input /mnt/input \
        --output /mnt/output
    "
}

# first
run_once "$INPUT1_HOST" "$OUTPUT1_HOST"
# second
run_once "$INPUT2_HOST" "$OUTPUT2_HOST"
