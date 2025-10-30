#!/bin/bash
#SBATCH --job-name=test_env
#SBATCH --output=output_%j.out
#SBATCH --error=err_%j.out
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gpus=nvidia_h100_80gb_hbm3_2g.20gb:1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=5:00
set -euo pipefail

SIF_IMG="/home/quanta/PartCrafter/partcrafter.sif"

module --force purge
module load StdEnv apptainer cuda/12.9

export NVIDIA_DRIVER_CAPABILITIES=compute,utility


apptainer exec --nv --cleanenv \
  --env PYOPENGL_PLATFORM=osmesa \
  --env LIBGL_ALWAYS_SOFTWARE=1 \
  "$SIF_IMG" bash -s <<'BASH'
set -euo pipefail

set +u
# 激活 conda
export PATH=/miniconda3/bin:$PATH
eval "$(conda shell.bash hook)"
conda activate partcrafter
set -u


# 运行 pyrender CPU 自检
python - <<'PY'
import os
os.environ["PYOPENGL_PLATFORM"] = "osmesa"  # 必须在任何 OpenGL 导入前

import numpy as np
from PIL import Image
import trimesh, pyrender
from OpenGL import GL, platform

print("backend:", type(platform.PLATFORM).__module__)  # 期望含 OpenGL.platform.osmesa

scene = pyrender.Scene(bg_color=[0,0,0,0], ambient_light=[0.1,0.1,0.1])
mesh = pyrender.Mesh.from_trimesh(trimesh.creation.icosphere(subdivisions=2, radius=1.0))
scene.add(mesh)
cam = pyrender.PerspectiveCamera(yfov=np.pi/3)
pose = np.array([[1,0,0,0],[0,1,0,0],[0,0,1,3],[0,0,0,1]])
scene.add(cam, pose=pose)
scene.add(pyrender.DirectionalLight(color=np.ones(3), intensity=3.0), pose=pose)

r = pyrender.OffscreenRenderer(256, 256)
color, _ = r.render(scene)

d = lambda b: b.decode() if b else None
print("GL_VENDOR  :", d(GL.glGetString(GL.GL_VENDOR)))
print("GL_RENDERER:", d(GL.glGetString(GL.GL_RENDERER)))
print("GL_VERSION :", d(GL.glGetString(GL.GL_VERSION)))
Image.fromarray(color).save("osmesa_pyrender_test.png")
print("wrote osmesa_pyrender_test.png")
r.delete()
PY
BASH
