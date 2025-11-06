# 继续使用同一环境变量
export PYOPENGL_PLATFORM=osmesa

python3 - <<'PY'
import os, numpy as np
os.environ['PYOPENGL_PLATFORM']='osmesa'

import pyrender
from PIL import Image

print("pyrender import: OK")
# 构造一个三角形 Primitive
positions=np.array([
    [-0.6,-0.6,0.0],
    [ 0.6,-0.6,0.0],
    [ 0.0, 0.6,0.0],
],dtype=np.float32)
indices=np.array([[0,1,2]],dtype=np.uint32)
normals=np.tile(np.array([[0,0,1]],dtype=np.float32),(3,1))

mat=pyrender.MetallicRoughnessMaterial(baseColorFactor=(1.0,0.4,0.2,1.0))
prim=pyrender.Primitive(positions=positions, indices=indices, normals=normals, material=mat)
mesh=pyrender.Mesh([prim])

scene=pyrender.Scene(bg_color=[0.1,0.2,0.3,1.0])
scene.add(mesh)

# 相机与光
cam=pyrender.PerspectiveCamera(yfov=np.pi/3.0)
pose=np.eye(4,dtype=np.float32); pose[2,3]=1.8
scene.add(cam, pose=pose)
light=pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
scene.add(light, pose=pose)

# 渲染
r=pyrender.OffscreenRenderer(256,256)
color, depth=r.render(scene)
r.delete()

Image.fromarray(color).save("/tmp/osmesa_pyrender.png")
print("saved      : /tmp/osmesa_pyrender.png")
print("mean(color):", float(color.mean()))
PY
