#!/bin/bash
#SBATCH --job-name=test_env
#SBATCH --output=output_%j.out
#SBATCH --error=err_%j.out
#SBATCH --gpus=nvidia_h100_80gb_hbm3_2g.20gb:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=5:00

set -euo pipefail

REPO_HOST="/home/quanta/PartCrafter"
REPO_MNT="/workspace"
SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"
CONDA_ENV_NAME="partcrafter"
CONDA_ROOT="/miniconda3"

module --force purge
module load StdEnv apptainer cuda/12.9

# host 侧先导出图形能力
export NVIDIA_DRIVER_CAPABILITIES=compute,utility

apptainer exec --nv --cleanenv \
  --bind "${REPO_HOST}:${REPO_MNT}" \
  --pwd "${REPO_MNT}" \
    --env PYOPENGL_PLATFORM=osmesa \
    --env OSMESA_LIBRARY=/usr/lib/x86_64-linux-gnu/libOSMesa.so.8 \
    --env GALLIUM_DRIVER=llvmpipe \
    --env LP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4} \
    --env LIBGL_ALWAYS_SOFTWARE=1 \
    --env MESA_LOADER_DRIVER_OVERRIDE=llvmpipe \
    --env QT_QPA_PLATFORM=offscreen \
    --env-unset __EGL_VENDOR_LIBRARY_FILENAMES \
    --env-unset EGL_PLATFORM \
    --env-unset DISPLAY \
  "$SIF_IMG" \
  bash -lc "
    set -eo pipefail
    export PATH=${CONDA_ROOT}/bin:\$PATH
    eval \"\$(conda shell.bash hook)\"
    conda activate ${CONDA_ENV_NAME}

    export PYTHONPATH=${REPO_MNT}:\${PYTHONPATH:-}

    python - <<'PY'
import os, ctypes
os.environ['PYOPENGL_PLATFORM']='osmesa'
os.environ['OSMESA_LIBRARY']='/usr/lib/x86_64-linux-gnu/libOSMesa.so.8'
os.environ['GALLIUM_DRIVER']='llvmpipe'
os.environ['MESA_LOADER_DRIVER_OVERRIDE']='llvmpipe'
os.environ['LIBGL_ALWAYS_SOFTWARE']='1'

from OpenGL import GL
from OpenGL.OSMesa import *

w, h = 64, 64

# 明确 minor 版本并传指针
attribs = (ctypes.c_int * 9)(
    OSMESA_FORMAT, OSMESA_RGBA,
    OSMESA_PROFILE, OSMESA_CORE_PROFILE,
    OSMESA_CONTEXT_MAJOR_VERSION, 4,
    OSMESA_CONTEXT_MINOR_VERSION, 5,
    0
)
ctx = OSMesaCreateContextAttrib(ctypes.byref(attribs), None)
assert ctx, "OSMesaCreateContextAttrib failed"

buf = (ctypes.c_ubyte * (w*h*4))()
ok = OSMesaMakeCurrent(ctx, ctypes.cast(buf, ctypes.c_void_p),
                       GL.GL_UNSIGNED_BYTE, w, h)
assert ok, "OSMesaMakeCurrent failed"

OSMesaPixelStore(OSMESA_Y_UP, 0)

print(GL.glGetString(GL.GL_RENDERER).decode())
print(GL.glGetString(GL.GL_VERSION).decode())

OSMesaDestroyContext(ctx)
PY
  "

