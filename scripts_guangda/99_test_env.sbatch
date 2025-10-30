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

# 关键：注入图形能力在 exec 之前导出
export NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,display,video

apptainer exec --nv --cleanenv \
  --bind "${REPO_HOST}:${REPO_MNT}" \
  --pwd "${REPO_MNT}" \
  --env PYOPENGL_PLATFORM=egl \
  --env EGL_PLATFORM=surfaceless \
  --env LD_LIBRARY_PATH='/.singularity.d/libs:/usr/lib/x86_64-linux-gnu' \
  "$SIF_IMG" \
  bash -lc "
    set -eo pipefail
    export PATH=${CONDA_ROOT}/bin:\$PATH
    eval \"\$(conda shell.bash hook)\"
    conda activate ${CONDA_ENV_NAME}
    export PYTHONPATH=${REPO_MNT}:\${PYTHONPATH:-}

    echo '[check] injected NVIDIA EGL libs:'
    ls -l /.singularity.d/libs/libEGL_nvidia.so* || { echo 'no nvidia EGL injected'; exit 1; }

    # 在容器内写 vendor JSON,并指向注入的 libEGL_nvidia.so.0
    cat > /tmp/10_nvidia.json <<EOF
{\"file_format_version\":\"1.0.0\",\"ICD\":{\"library_path\":\"libEGL_nvidia.so.0\"}}
EOF
    export __EGL_VENDOR_LIBRARY_FILENAMES=/tmp/10_nvidia.json

    # conda activate 可能改动了 LD_LIBRARY_PATH, 重新前置注入库
    export LD_LIBRARY_PATH=/.singularity.d/libs:/usr/lib/x86_64-linux-gnu:\$LD_LIBRARY_PATH

    echo '[check] /dev/nvidia*:'
    ls -l /dev/nvidia* || true

    python - <<'PY'
from ctypes import c_void_p
from OpenGL.raw.EGL.EXT.device_enumeration import eglQueryDevicesEXT
N=16
arr=(c_void_p*N)()
ok=eglQueryDevicesEXT(N, arr, None)
cnt=sum(1 for p in arr if p)
print('egl devices ok=', bool(ok), 'count=', cnt)
PY

    python - <<'PY'
from OpenGL.GL import glGetString, GL_VENDOR, GL_RENDERER
import pyrender
r=pyrender.OffscreenRenderer(64,64)
print('[GL_VENDOR]', glGetString(GL_VENDOR).decode())
print('[GL_RENDERER]', glGetString(GL_RENDERER).decode())
PY
  "
