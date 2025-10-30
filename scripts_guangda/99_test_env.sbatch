#!/bin/bash
#SBATCH --job-name=test_env
#SBATCH --output=testenv_%j.out
#SBATCH --error=testenv_%j.err
#SBATCH --gpus=nvidia_h100_80gb_hbm3_2g.20gb:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=1:00:00

set -euo pipefail

REPO_HOST="/home/quanta/PartCrafter"
REPO_MNT="/workspace"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"

module --force purge
module load StdEnv apptainer cuda/12.9

# host 侧先导出图形能力
export NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,display,video

apptainer exec --nv --cleanenv \
  --bind "${REPO_HOST}:${REPO_MNT}" \
  --bind "/usr/share/glvnd/egl_vendor.d:/usr/share/glvnd/egl_vendor.d:ro" \
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

    # conda 可能改了 LD_LIBRARY_PATH，这里再前置一次注入库
    export LD_LIBRARY_PATH=/.singularity.d/libs:/usr/lib/x86_64-linux-gnu:\$LD_LIBRARY_PATH
    export PYTHONPATH=${REPO_MNT}:\${PYTHONPATH:-}

    # 自检：应看到 NVIDIA EGL 被注入
    ls -l /.singularity.d/libs/libEGL_nvidia.so.0 || { echo 'no nvidia EGL injected'; exit 1; }

    # 应打印 NVIDIA Corporation 和 GPU 型号
    python - <<'PY'
from OpenGL.GL import glGetString, GL_VENDOR, GL_RENDERER
import pyrender
r = pyrender.OffscreenRenderer(64, 64)
print('[GL_VENDOR]', glGetString(GL_VENDOR).decode())
print('[GL_RENDERER]', glGetString(GL_RENDERER).decode())
PY

    # 你的实际任务
    python -m datasets.preprocess.preprocess --input /mnt/input --output /mnt/output
  "

