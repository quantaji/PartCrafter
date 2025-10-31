#!/bin/bash
#SBATCH --job-name=render_pipeline_cpu
#SBATCH --output=outlog_%j.out
#SBATCH --error=errlog_%j.out
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=24:00:00

set -euo pipefail


REPO_HOST="/home/quanta/PartCrafter"
REPO_MNT="/workspace"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"
PIPELINE_REL="scripts_guangda/03_10_preprocessing_render.py"  


# INPUT_HOST="/scratch/quanta/objaverse_selected"
# OUTPUT_HOST="/scratch/quanta/objaverse_partpacker_preprocessed"
INPUT_HOST="/scratch/quanta/partverse_selected"
OUTPUT_HOST="/scratch/quanta/partverse_partpacker_preprocessed"

# 分片
NUM_SHARDS=1
SHARD_INDEX=0
IGNORE_EXISTING_FLAG="--ignore_existing"   # 需要则取消注释

mkdir -p "$OUTPUT_HOST"

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

      if [ ! -f ${PIPELINE_REL} ]; then
        echo 'pipeline脚本未找到: ${PIPELINE_REL}' >&2
        exit 1
      fi

      python ${PIPELINE_REL} \
        --src_dir /mnt/input \
        --tgt_dir /mnt/output \
        --num_shards ${NUM_SHARDS} \
        --shard_index ${SHARD_INDEX} \
        ${IGNORE_EXISTING_FLAG:-}
    "
}

# 执行
run_once "$INPUT_HOST" "$OUTPUT_HOST"
