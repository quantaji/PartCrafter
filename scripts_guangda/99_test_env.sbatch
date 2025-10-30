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

SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"

module --force purge
module load StdEnv apptainer cuda/12.9

VENDOR_DIR="${SLURM_TMPDIR:-/tmp}/egl_vendor_mesa"
mkdir -p "$VENDOR_DIR"
cat >"$VENDOR_DIR/50_mesa.json" <<'JSON'
{
  "file_format_version": "1.0.0",
  "ICD": { "library_path": "libEGL_mesa.so.0" }
}
JSON

apptainer exec --nv --cleanenv \
  --bind "$VENDOR_DIR:/usr/share/glvnd/egl_vendor.d" \
  --env PYOPENGL_PLATFORM=egl \
  --env EGL_PLATFORM=surfaceless \
  --env __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json \
  --env LIBGL_ALWAYS_SOFTWARE=1 \
  --env MESA_LOADER_DRIVER_OVERRIDE=llvmpipe \
  --env GALLIUM_DRIVER=llvmpipe \
  --env LP_NUM_THREADS=${SLURM_CPUS_PER_TASK:-4} \
  --env QT_QPA_PLATFORM=offscreen \
  --env LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libstdc++.so.6 \
  "$SIF_IMG" bash -s <<'BASH'
set -euo pipefail

set +u
# 激活 conda
export PATH=/miniconda3/bin:$PATH
eval "$(conda shell.bash hook)"
conda activate partcrafter
set -u

# 系统 libstdc++ 优先，避免 GLIBCXX 冲突
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH-}

# 运行 pyrender CPU 自检
python - <<'PY'
import os, numpy as np
# 兜底
os.environ.setdefault("PYOPENGL_PLATFORM","egl")
os.environ.setdefault("EGL_PLATFORM","surfaceless")
os.environ.setdefault("__EGL_VENDOR_LIBRARY_FILENAMES","/usr/share/glvnd/egl_vendor.d/50_mesa.json")
os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE","1")
os.environ.setdefault("MESA_LOADER_DRIVER_OVERRIDE","llvmpipe")
os.environ.setdefault("GALLIUM_DRIVER","llvmpipe")

import pyrender, trimesh
from PIL import Image
from OpenGL import GL

def look_at(eye, target, up):
    eye=np.array(eye,dtype=np.float32); target=np.array(target,dtype=np.float32); up=np.array(up,dtype=np.float32)
    z=eye-target; z/=np.linalg.norm(z); x=np.cross(up,z); x/=np.linalg.norm(x); y=np.cross(z,x)
    m=np.eye(4,dtype=np.float32); m[:3,0]=x; m[:3,1]=y; m[:3,2]=z; m[:3,3]=eye; return m

mesh=trimesh.creation.icosphere(subdivisions=2,radius=1.0)
mesh.visual.vertex_colors=[200,60,60,255]
pm=pyrender.Mesh.from_trimesh(mesh,smooth=True)

scene=pyrender.Scene(bg_color=[255,255,255,0]); scene.add(pm)
scene.add(pyrender.DirectionalLight(color=np.ones(3),intensity=3.0), pose=np.eye(4))
cam=pyrender.PerspectiveCamera(yfov=np.deg2rad(45.0),aspectRatio=1.0,znear=0.05,zfar=10.0)
scene.add(cam, pose=look_at([3,2,3],[0,0,0],[0,1,0]))

r=pyrender.OffscreenRenderer(256,256)
renderer=GL.glGetString(GL.GL_RENDERER); version=GL.glGetString(GL.GL_VERSION)
print("GL_RENDERER:", renderer.decode() if renderer else "None")
print("GL_VERSION :", version.decode() if version else "None")

color,depth=r.render(scene); r.delete()
Image.fromarray(color).save("/tmp/pyrender_cpu_test.png")
print("WROTE: /tmp/pyrender_cpu_test.png")
PY
BASH
