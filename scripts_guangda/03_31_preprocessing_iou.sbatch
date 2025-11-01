#!/bin/bash
#SBATCH --job-name=iou_stage
#SBATCH --output=outlog_%j.out
#SBATCH --error=errlog_%j.out
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=24:00:00

set -euo pipefail

# 路径
REPO_HOST="/home/quanta/PartCrafter"
REPO_MNT="/workspace"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
CONDA_ROOT="/miniconda3"
CONDA_ENV_NAME="partcrafter"
IOU_REL="scripts_guangda/03_30_preprocessing_iou.py"  # 置为前述第4部分脚本相对路径

INPUT_HOST="/scratch/quanta/objaverse_selected"
OUTPUT_HOST="/scratch/quanta/objaverse_partpacker_preprocessed"
# INPUT_HOST="/scratch/quanta/partverse_selected"
# OUTPUT_HOST="/scratch/quanta/partverse_partpacker_preprocessed"

mkdir -p "$OUTPUT_HOST"

# 分片参数
NUM_SHARDS=10
SHARD_INDEX=0
IGNORE_EXISTING_FLAG="--ignore_existing"

# 计算环境
module --force purge
module load StdEnv apptainer

run_once () {
  local IN_HOST="$1"
  local OUT_HOST="$2"

  apptainer exec --cleanenv \
    --bind "${REPO_HOST}:${REPO_MNT}" \
    --bind "${IN_HOST}:/mnt/input" \
    --bind "${OUT_HOST}:/mnt/output" \
    --pwd "${REPO_MNT}" \
    "$SIF_IMG" \
    bash -lc "
      set -eo pipefail
      export PATH=${CONDA_ROOT}/bin:\$PATH
      eval \"\$(conda shell.bash hook)\"
      conda activate ${CONDA_ENV_NAME}
      export PYTHONPATH=${REPO_MNT}:\${PYTHONPATH:-}

      if [ ! -f ${IOU_REL} ]; then
        echo '脚本未找到: ${IOU_REL}' >&2
        exit 1
      fi

      python ${IOU_REL} \
        --src_dir /mnt/input \
        --tgt_dir /mnt/output \
        --num_shards ${NUM_SHARDS} \
        --shard_index ${SHARD_INDEX} \
        ${IGNORE_EXISTING_FLAG}
    "
}

run_once "$INPUT_HOST" "$OUTPUT_HOST"
