#!/bin/bash
#SBATCH --job-name=rmbg_stage
#SBATCH --output=outlog_%j.out
#SBATCH --error=errlog_%j.out
#SBATCH --gpus=nvidia_h100_80gb_hbm3_1g.10gb:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=32G
#SBATCH --time=1:00:00

set -euo pipefail

# 路径
REPO_HOST="/home/quanta/PartCrafter"
REPO_MNT="/workspace"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
CONDA_ROOT="/miniconda3"
CONDA_ENV_NAME="partcrafter"
RMBG_REL="scripts_guangda/03_20_preprocesing_rmbg.py"   # 修改为上面这段脚本的相对路径

INPUT_HOST="/scratch/quanta/objaverse_partpacker_preprocessed"
OUTPUT_HOST="/scratch/quanta/objaverse_partpacker_preprocessed"
# INPUT_HOST="/scratch/quanta/partverse_partpacker_preprocessed"
# OUTPUT_HOST="/scratch/quanta/partverse_partpacker_preprocessed"

mkdir -p "$OUTPUT_HOST" "$OUTPUT_HOST"

# 分片参数
NUM_SHARDS=1
SHARD_INDEX=0
IGNORE_EXISTING_FLAG="--ignore_existing"  # 需要则保留

# 计算环境
module --force purge
module load StdEnv apptainer cuda/12.9
export NVIDIA_DRIVER_CAPABILITIES=compute,utility

run_once () {
  local IN_HOST="$1"
  local OUT_HOST="$2"

  apptainer exec --nv --cleanenv \
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

      if [ ! -f ${RMBG_REL} ]; then
        echo '脚本未找到: ${RMBG_REL}' >&2
        exit 1
      fi
      if [ ! -d pretrained_weights/RMBG-1.4 ]; then
        echo '权重目录缺失: pretrained_weights/RMBG-1.4' >&2
        exit 1
      fi

      python ${RMBG_REL} \
        --src_dir /mnt/input \
        --tgt_dir /mnt/output \
        --num_shards ${NUM_SHARDS} \
        --shard_index ${SHARD_INDEX} \
        ${IGNORE_EXISTING_FLAG}
    "
}

run_once "$INPUT_HOST" "$OUTPUT_HOST"
