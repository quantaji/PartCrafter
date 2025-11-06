# 固定 OSMesa
export LIBGL_ALWAYS_SOFTWARE=1
export MESA_LOADER_DRIVER_OVERRIDE=softpipe
export GALLIUM_DRIVER=softpipe
export LP_NUM_THREADS=1
export OMP_NUM_THREADS=1
export PYOPENGL_PLATFORM=osmesa

python3 - <<'PY'
import ctypes, ctypes.util, numpy as np
from OpenGL import GL
from PIL import Image

# 找到并加载 OSMesa
path = ctypes.util.find_library("OSMesa") or "libOSMesa.so.8"
OS = ctypes.CDLL(path)

# 常量与签名
OSMESA_RGBA = 0x1908         # == GL_RGBA
GL_UNSIGNED_BYTE = 0x1401
OS.OSMesaCreateContextExt.restype = ctypes.c_void_p
OS.OSMesaCreateContextExt.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
OS.OSMesaMakeCurrent.restype = ctypes.c_int
OS.OSMesaMakeCurrent.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int]
OS.OSMesaDestroyContext.argtypes = [ctypes.c_void_p]

W, H = 128, 128
buf = (ctypes.c_ubyte * (W*H*4))()

ctx = OS.OSMesaCreateContextExt(OSMESA_RGBA, 24, 8, 0, None)
ok  = bool(ctx) and bool(OS.OSMesaMakeCurrent(ctx, buf, GL_UNSIGNED_BYTE, W, H))
print("OSMesa so  :", path)
print("OSMesa ctx :", "OK" if ok else "FAIL")
if not ok:
    raise SystemExit(1)

GL.glDisable(GL.GL_DITHER)
GL.glPixelStorei(GL.GL_PACK_ALIGNMENT, 1)
GL.glViewport(0, 0, W, H)
GL.glClearColor(0.1, 0.2, 0.3, 1.0)
GL.glClear(GL.GL_COLOR_BUFFER_BIT)

# 打印渲染器信息
vend = GL.glGetString(GL.GL_VENDOR)
rend = GL.glGetString(GL.GL_RENDERER)
vers = GL.glGetString(GL.GL_VERSION)
print("GL_VENDOR  :", vend.decode() if vend else "None")
print("GL_RENDERER:", rend.decode() if rend else "None")
print("GL_VERSION :", vers.decode() if vers else "None")

# 读回并保存；OSMesa 缓冲 top-down
arr = np.frombuffer(buf, dtype=np.uint8).reshape(H, W, 4)
rgb = arr[::-1, :, :3]
Image.fromarray(rgb, "RGB").save("/tmp/osmesa_pyopengl.png")
print("saved      : /tmp/osmesa_pyopengl.png")

OS.OSMesaDestroyContext(ctx)
PY
