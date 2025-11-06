set -euo pipefail

set +eu
eval "$(conda shell.bash hook)"
conda activate partcrafter
set -eu


unset DISPLAY
export PYOPENGL_PLATFORM=egl
export PYGLET_HEADLESS=true          # 重要：让 pyglet 进入 headless
export PYGLET_PLATFORM=egl           # 让 pyglet 选 EGL 后端
export EGL_PLATFORM=surfaceless
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json

python3 - <<'PY'
import os; os.environ.setdefault("PYGLET_HEADLESS","true")
os.environ.setdefault("PYGLET_PLATFORM","egl")
os.environ.setdefault("PYOPENGL_PLATFORM","egl")
os.environ.setdefault("EGL_PLATFORM","surfaceless")

# 关键：避免触发 viewer 的 import 副作用
from pyrender import Scene, Mesh, PerspectiveCamera, OffscreenRenderer
import numpy as np, trimesh

scene = Scene(bg_color=[0.2,0.2,0.2,1.0])
mesh = trimesh.creation.icosphere(subdivisions=2, radius=1.0)
scene.add(Mesh.from_trimesh(mesh, smooth=True))
scene.add(PerspectiveCamera(yfov=np.deg2rad(45.0)),
          pose=np.array([[1,0,0,0],[0,1,0,0],[0,0,1,3.5],[0,0,0,1]], np.float32))

r = OffscreenRenderer(256,256)
color, depth = r.render(scene); r.delete()

from OpenGL import GL
to_s=lambda b: b.decode() if isinstance(b,(bytes,bytearray)) else str(b)
print("GL_VENDOR   :", to_s(GL.glGetString(GL.GL_VENDOR)))
print("GL_RENDERER :", to_s(GL.glGetString(GL.GL_RENDERER)))

from PIL import Image; Image.fromarray(color).save("/tmp/pyrender_ok.png")
print("wrote /tmp/pyrender_ok.png")
PY
