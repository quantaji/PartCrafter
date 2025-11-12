import math
import os
from typing import List, Optional, Tuple, Union

import numpy as np
import torch
import trimesh
from diffusers.utils import export_to_video
from PIL import Image
from pytorch3d.renderer import (
    DirectionalLights,
    FoVPerspectiveCameras,
    HardPhongShader,
    MeshRasterizer,
    MeshRenderer,
    RasterizationSettings,
    TexturesVertex,
)
from pytorch3d.renderer.cameras import look_at_view_transform
from pytorch3d.structures import Meshes
from pytorch3d.transforms import so3_exponential_map
from torchvision.utils import make_grid

from src.utils.typing_utils import *


@torch.no_grad()
def render(
    meshes,  # pytorch3d.structures.Meshes，batch=1
    renderer: MeshRenderer,  # 含 rasterizer 与 shader
    cameras,  # FoVPerspectiveCameras 或兼容相机
    lights: DirectionalLights | None = None,
    normalize_depth: bool = False,
    return_type: str = "pil",  # "tensor" | "ndarray" | "pil"
):
    device = meshes.device

    # 未传光时：零辐照，避免 PyTorch3D 默认点光
    if lights is None:
        lights = DirectionalLights(
            device=device,
            ambient_color=[[0.0, 0.0, 0.0]],
            diffuse_color=[[0.0, 0.0, 0.0]],
            specular_color=[[0.0, 0.0, 0.0]],
            direction=[[0.0, 0.0, 1.0]],
        )

    # 仅一次栅格化：先 raster，再 shader
    frags = renderer.rasterizer(meshes, cameras=cameras)
    images = renderer.shader(fragments=frags, meshes=meshes, cameras=cameras, lights=lights)  # (1,H,W,4) in [0,1]

    # 颜色张量 uint8 (H,W,3)
    color_t = (images[0, ..., :3].clamp(0, 1) * 255.0).to(torch.uint8)

    # 深度张量 (H,W)
    depth_t = frags.zbuf[0, ..., 0]

    # 归一化规则：return_type 为 "pil" 时强制归一化为 uint8；否则仅在 normalize_depth=True 时归一化
    force_norm_for_pil = return_type == "pil"
    if normalize_depth or force_norm_for_pil:
        mask = torch.isfinite(depth_t)
        depth_u8 = torch.zeros_like(depth_t, dtype=torch.uint8)
        if mask.any():
            d = depth_t[mask]
            denom = torch.clamp(d.max() - d.min(), min=torch.finfo(d.dtype).eps)
            depth_u8[mask] = ((d - d.min()) / denom * 255.0).to(torch.uint8)
        depth_t = depth_u8

    # 按需返回类型
    if return_type == "tensor":
        return color_t, depth_t

    elif return_type == "ndarray":
        color_np = color_t.detach().cpu().numpy()
        depth_np = depth_t.detach().cpu().numpy()
        return color_np, depth_np

    elif return_type == "pil":
        color_np = color_t.detach().cpu().numpy()
        depth_np = depth_t.detach().cpu().numpy()
        return Image.fromarray(color_np), Image.fromarray(depth_np)

    else:
        raise ValueError(f"Unknown return_type: {return_type}")


def create_circular_camera_positions(
    num_views: int,
    radius: float,
    axis: torch.Tensor,  # (3,), 任意 device/dtype；将被归一化
) -> torch.Tensor:
    """
    返回形状 (N,3) 的位置张量。语义与原实现一致：
    先在 XZ 平面生成圆，再把世界 Y 轴对齐到 axis 后整体旋转。
    """
    axis = axis / torch.linalg.norm(axis)
    device, dtype = axis.device, axis.dtype

    idx = torch.arange(num_views, device=device, dtype=dtype)
    theta = 2.0 * torch.pi * idx / float(num_views)
    st, ct = torch.sin(theta), torch.cos(theta)

    P0 = torch.stack([st * radius, torch.zeros_like(st), ct * radius], dim=1)  # (N,3)

    y_up = torch.tensor([0.0, 1.0, 0.0], device=device, dtype=dtype)
    v = torch.cross(y_up, axis)
    c = torch.clamp(torch.dot(y_up, axis), -1.0, 1.0)  # cos
    s = torch.linalg.norm(v)  # sin
    eps = torch.finfo(dtype).eps

    if s.item() <= eps:
        if c.item() > 0.0:
            R_axis = torch.eye(3, device=device, dtype=dtype)
        else:
            # 180° 绕任一与 y 正交轴；选 x 轴
            log_rot = torch.tensor([torch.pi, 0.0, 0.0], device=device, dtype=dtype)
            R_axis = so3_exponential_map(log_rot.unsqueeze(0))[0]
    else:
        u = v / s
        theta0 = torch.atan2(s, c)
        log_rot = u * theta0
        R_axis = so3_exponential_map(log_rot.unsqueeze(0))[0]  # (3,3)

    # 批量右乘 R^T
    return P0 @ R_axis.transpose(0, 1)  # (N,3)


def create_circular_camera_poses(
    num_views: int,
    radius: float,
    axis: torch.Tensor,  # (3,), 任意 device/dtype；将被归一化
) -> torch.Tensor:
    """
    返回形状 (N,4,4) 的齐次位姿张量。语义与原实现一致：
    canonical_pose 放在 +Z 距离 radius，随后对每个 θ 绕给定 axis 旋转：pose = R(θ,axis) @ canonical_pose。
    """
    axis = axis / torch.linalg.norm(axis)
    device, dtype = axis.device, axis.dtype

    # 批量角度
    idx = torch.arange(num_views, device=device, dtype=dtype)
    theta = 2.0 * torch.pi * idx / float(num_views)  # (N,)
    rotvecs = axis.unsqueeze(0) * theta.unsqueeze(1)  # (N,3)
    R = so3_exponential_map(rotvecs)  # (N,3,3)

    # 平移 = R @ [0,0,radius]
    vz = torch.tensor([0.0, 0.0, radius], device=device, dtype=dtype).expand(num_views, 3, 1)  # (N,3,1)
    t = torch.bmm(R, vz).squeeze(-1)  # (N,3)

    # 组装 4x4
    last_row = torch.tensor([0.0, 0.0, 0.0, 1.0], device=device, dtype=dtype).expand(num_views, 1, 4)
    poses = torch.zeros((num_views, 4, 4), device=device, dtype=dtype)
    poses[:, :3, :3] = R
    poses[:, :3, 3] = t
    poses[:, 3:, :] = last_row
    return poses  # (N,4,4)


@torch.no_grad()
def create_camera_pose_on_sphere(
    azimuth: float = 0.0,  # degrees
    elevation: float = 0.0,  # degrees
    radius: float = 3.5,
    *,
    device: Optional[torch.device] = None,
    dtype: Optional[torch.dtype] = None,
) -> torch.Tensor:
    """
    返回 camera->world 的 4x4 齐次矩阵。与原语义一致：
    相机在半径为 radius 的球面上看原点，up = [0,1,0]。
    """
    if device is None:
        device = torch.device("cpu")
    if dtype is None:
        dtype = torch.get_default_dtype()

    # world->camera
    R_wc, T_wc = look_at_view_transform(dist=radius, elev=elevation, azim=azimuth, degrees=True, device=device)
    cams = FoVPerspectiveCameras(device=device, R=R_wc, T=T_wc)
    pose_cw = cams.get_world_to_view_transform().inverse().get_matrix()[0]  # (4,4)
    return pose_cw.to(dtype=dtype)


def trimesh_to_pytorch3d(
    tm: Union[trimesh.Trimesh, trimesh.Scene],
    device: Optional[Union[int, str, torch.device]] = None,
) -> Meshes:

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # 收集几何并复制；不做 graph 变换
    if isinstance(tm, trimesh.Trimesh):
        parts = [tm.copy()]

    elif isinstance(tm, trimesh.Scene):
        parts = []
        # 优先用 geometry.values() 的列表
        try:
            geoms = list(tm.geometry.values())
            parts.extend([g.copy() for g in geoms if isinstance(g, trimesh.Trimesh)])
        except Exception:
            pass

        # 若仍为空，容错 nodes_geometry 的几种形态
        if not parts:
            try:
                ng = tm.graph.nodes_geometry
                for it in list(ng):
                    if isinstance(it, trimesh.Trimesh):
                        parts.append(it.copy())
                    elif isinstance(it, (list, tuple)) and len(it) == 2:
                        _, gk = it
                        g = tm.geometry.get(gk, None)
                        if isinstance(g, trimesh.Trimesh):
                            parts.append(g.copy())
                    elif isinstance(it, str):
                        g = tm.geometry.get(it, None)
                        if isinstance(g, trimesh.Trimesh):
                            parts.append(g.copy())
            except Exception:
                pass

        if not parts:
            raise ValueError("Scene 中没有可用的三角网格")

    else:
        raise TypeError("输入必须是 trimesh.Trimesh 或 trimesh.Scene")

    # 如有多个网格，合并
    tmesh = parts[0] if len(parts) == 1 else trimesh.util.concatenate(parts)

    if tmesh.vertices is None or tmesh.faces is None or len(tmesh.faces) == 0:
        raise ValueError("网格为空或缺少顶点/面")

    # 颜色内联 bake：vertex > texture-bake > face > white
    vc = getattr(tmesh.visual, "vertex_colors", None)
    if vc is None or len(vc) != len(tmesh.vertices):
        kind = getattr(tmesh.visual, "kind", None)
        done = False
        if kind == "texture":
            try:
                tmesh.visual = tmesh.visual.to_color()  # 纹理采样到顶点色
                done = True
            except Exception:
                done = False
        if not done:
            fc = getattr(tmesh.visual, "face_colors", None)
            if fc is not None and len(fc) == len(tmesh.faces):
                vcol = np.ones((len(tmesh.vertices), 4), dtype=np.uint8) * 255
                v_idx = tmesh.faces.reshape(-1)
                vcol[v_idx] = np.repeat(fc, repeats=3, axis=0)
                tmesh.visual.vertex_colors = vcol
            else:
                tmesh.visual.vertex_colors = np.ones((len(tmesh.vertices), 4), dtype=np.uint8) * 255

    # 转 torch
    verts = torch.as_tensor(np.asarray(tmesh.vertices, np.float32), device=device)
    faces = torch.as_tensor(np.asarray(tmesh.faces, np.int64), device=device)

    vc = getattr(tmesh.visual, "vertex_colors", None)
    if vc is not None and len(vc) == len(tmesh.vertices):
        v_rgb = torch.as_tensor(vc[:, :3].astype(np.float32) / 255.0, device=device)
    else:
        v_rgb = torch.ones((verts.shape[0], 3), dtype=torch.float32, device=device)

    textures = TexturesVertex(verts_features=v_rgb.unsqueeze(0))  # (1,V,3)
    return Meshes(verts=[verts], faces=[faces], textures=textures)


@torch.no_grad()
def render_single_view(
    mesh: Meshes,
    azimuth: float = 0.0,
    elevation: float = 0.0,
    radius: float = 3.5,
    image_size: Tuple[int, int] = (512, 512),  # (H, W)
    fov: float = 40.0,
    light_intensity: Optional[float] = 5.0,
    num_env_lights: int = 0,
    znear: float = 0.1,
    zfar: float = 10.0,
    normalize_depth: bool = False,
    flags: int = 0,  # 占位
    return_depth: bool = False,
    return_type: str = "pil",  # "tensor" | "ndarray" | "pil"
) -> Union[
    torch.Tensor,
    np.ndarray,
    Image.Image,
    Tuple[torch.Tensor, torch.Tensor],
    Tuple[np.ndarray, np.ndarray],
    Tuple[Image.Image, Image.Image],
]:
    if not isinstance(mesh, Meshes):
        raise ValueError("mesh 必须是 pytorch3d.structures.Meshes")
    # 固定 batch=1
    if len(mesh) != 1:
        raise ValueError("仅支持 batch=1")

    device = mesh.device
    dtype = mesh.verts_padded().dtype
    H, W = int(image_size[0]), int(image_size[1])

    pose_cw = create_camera_pose_on_sphere(
        azimuth=azimuth,
        elevation=elevation,
        radius=radius,
        device=device,
        dtype=dtype,
    )
    R_cw = pose_cw[:3, :3]
    t_cw = pose_cw[:3, 3]
    R_wc = R_cw.transpose(0, 1)
    T_wc = -R_wc @ t_cw

    # 用 (R_wc, T_wc) 构建相机；注意 aspect_ratio = W / H，image_size = (H, W)
    cameras = FoVPerspectiveCameras(
        device=device,
        R=R_wc.unsqueeze(0),
        T=T_wc.unsqueeze(0),
        fov=fov,
        degrees=True,
        znear=znear,
        zfar=zfar,
        aspect_ratio=float(W) / float(H),
    )

    # 渲染器：一次 raster
    raster = MeshRasterizer(
        cameras=cameras,
        raster_settings=RasterizationSettings(image_size=(H, W), faces_per_pixel=1, cull_backfaces=False),
    )  # (H, W)
    shader = HardPhongShader(device=device, cameras=cameras)
    renderer = MeshRenderer(rasterizer=raster, shader=shader)

    # 栅格化一次
    frags = raster(mesh, cameras=cameras)

    # 计算光照
    imgs_acc = None
    if num_env_lights > 0:
        if light_intensity is None:
            # 无强度则等价无光
            diff = 0.0
        else:
            diff = float(light_intensity)

        # 环形多盏方向光：等分方位角，方向指向原点
        thetas = 2.0 * torch.pi * torch.arange(num_env_lights, device=device, dtype=dtype) / float(num_env_lights)
        dirs = torch.stack([-torch.sin(thetas), torch.zeros_like(thetas), -torch.cos(thetas)], dim=1)  # (K,3)

        imgs_list = []
        for k in range(num_env_lights):
            v = dirs[k].unsqueeze(0)  # (1,3)
            lights_k = DirectionalLights(
                device=device,
                direction=v,
                ambient_color=[[0.0, 0.0, 0.0]],
                diffuse_color=[[diff, diff, diff]],
                specular_color=[
                    [0.0, 0.0, 0.0],
                ],
            )
            img_k = renderer.shader(
                fragments=frags,
                meshes=mesh,
                cameras=cameras,
                lights=lights_k,
            )  # (1,H,W,4)
            imgs_list.append(img_k)
        imgs_acc = torch.clamp(torch.sum(torch.stack(imgs_list, dim=0), dim=0), 0.0, 1.0)  # (1,H,W,4)

    else:
        # 单盏或无光
        if light_intensity is None:
            # 零辐照，得到纯黑着色（深度仍可用）
            lights = DirectionalLights(
                device=device,
                ambient_color=[[0.0, 0.0, 0.0]],
                diffuse_color=[[0.0, 0.0, 0.0]],
                specular_color=[[0.0, 0.0, 0.0]],
                direction=[[0.0, 0.0, 1.0]],
            )
        else:
            # 相机方向光：方向 = 从相机位置指向原点
            cam_pos = t_cw  # camera->world 的平移即相机位置，shape (3,)
            v = -cam_pos / torch.clamp(cam_pos.norm(), min=torch.finfo(dtype).eps)
            diff = float(light_intensity)
            lights = DirectionalLights(
                device=device,
                direction=v.view(1, 3),
                ambient_color=[[0.0, 0.0, 0.0]],
                diffuse_color=[[diff, diff, diff]],
                specular_color=[[0.0, 0.0, 0.0]],
            )

        imgs_acc = renderer.shader(fragments=frags, meshes=mesh, cameras=cameras, lights=lights)  # (1,H,W,4)

    # 颜色
    color_t = (imgs_acc[0, ..., :3].clamp(0, 1) * 255.0).to(torch.uint8)  # (H,W,3)

    # 深度
    depth_t = frags.zbuf[0, ..., 0]  # (H,W)
    force_norm_for_pil = return_type == "pil"
    if normalize_depth or force_norm_for_pil:
        mask = torch.isfinite(depth_t)
        depth_u8 = torch.zeros_like(depth_t, dtype=torch.uint8)
        if mask.any():
            d = depth_t[mask]
            denom = torch.clamp(d.max() - d.min(), min=torch.finfo(d.dtype).eps)
            depth_u8[mask] = ((d - d.min()) / denom * 255.0).to(torch.uint8)
        depth_t = depth_u8

    # 返回类型
    if return_type == "tensor":
        if return_depth:
            return color_t, depth_t
        return color_t

    elif return_type == "ndarray":
        color_np = color_t.detach().cpu().numpy()
        depth_np = depth_t.detach().cpu().numpy()
        if return_depth:
            return color_np, depth_np
        return color_np

    elif return_type == "pil":
        color_np = color_t.detach().cpu().numpy()
        depth_np = depth_t.detach().cpu().numpy()
        color_img = Image.fromarray(color_np)
        depth_img = Image.fromarray(depth_np)
        if return_depth:
            return color_img, depth_img
        return color_img

    else:
        raise ValueError(f"Unknown return_type: {return_type}")


@torch.no_grad()
def render_normal_single_view(
    mesh: Meshes,
    azimuth: float = 0.0,  # degrees
    elevation: float = 0.0,  # degrees
    radius: float = 3.5,
    image_size: Tuple[int, int] = (512, 512),  # (H, W)
    fov: float = 40.0,
    light_intensity: Optional[float] = 5.0,
    znear: float = 0.1,
    zfar: float = 10.0,
    normalize_depth: bool = False,
    flags: int = 0,  # 占位，保持签名兼容；不使用
    return_depth: bool = False,
    return_type: str = "tensor",  # "tensor" | "ndarray" | "pil"
) -> Union[
    torch.Tensor,
    np.ndarray,
    Image.Image,
    Tuple[torch.Tensor, torch.Tensor],
    Tuple[np.ndarray, np.ndarray],
    Tuple[Image.Image, Image.Image],
]:
    if not isinstance(mesh, Meshes):
        raise ValueError("mesh 必须是 pytorch3d.structures.Meshes")
    if len(mesh) != 1:
        raise ValueError("仅支持 batch=1")

    device = mesh.device
    dtype = mesh.verts_padded().dtype

    # 计算顶点法线并映射为颜色 [0,1]
    normals_packed = mesh.verts_normals_packed()  # (V,3)
    colors_packed = ((normals_packed + 1.0) * 0.5).clamp(0, 1)  # (V,3) in [0,1]
    colors = colors_packed.unsqueeze(0)  # (1,V,3)

    # 用法线颜色替换顶点纹理
    tex = TexturesVertex(verts_features=colors.to(device=device, dtype=dtype))
    colored_mesh = Meshes(verts=mesh.verts_list(), faces=mesh.faces_list(), textures=tex).to(device)  # 保持几何不变

    # 直接复用已实现的渲染入口；其内部已处理 H×W、单次 raster、返回类型等
    return render_single_view(
        colored_mesh,
        azimuth=azimuth,
        elevation=elevation,
        radius=radius,
        image_size=image_size,
        fov=fov,
        light_intensity=light_intensity,
        num_env_lights=0,  # 与原函数一致，未引入额外环境光
        znear=znear,
        zfar=zfar,
        normalize_depth=normalize_depth,
        flags=flags,
        return_depth=return_depth,
        return_type=return_type,
    )


@torch.no_grad()
def render_views_around_mesh(
    mesh: Meshes,
    num_views: int = 36,
    radius: float = 3.5,
    axis: torch.Tensor = torch.tensor([0.0, 1.0, 0.0]),
    image_size: Tuple[int, int] = (512, 512),  # (H, W)
    fov: float = 40.0,
    light_intensity: Optional[float] = 5.0,
    znear: float = 0.1,
    zfar: float = 10.0,
    normalize_depth: bool = False,
    flags: int = 0,  # 占位，不使用
    return_depth: bool = False,
    return_type: str = "pil",  # "pil" | "ndarray" | "tensor"
) -> Union[
    torch.Tensor,
    np.ndarray,
    Image.Image,
    Tuple[torch.Tensor, torch.Tensor],
    Tuple[np.ndarray, np.ndarray],
    Tuple[Image.Image, Image.Image],
]:
    if not isinstance(mesh, Meshes):
        raise ValueError("mesh 必须是 pytorch3d.structures.Meshes")
    if len(mesh) != 1:
        raise ValueError("仅支持 batch=1")

    device = mesh.device
    dtype = mesh.verts_padded().dtype
    H, W = int(image_size[0]), int(image_size[1])

    # 统一 axis 的 device/dtype
    axis = (axis / torch.linalg.norm(axis)).to(device=device, dtype=dtype)

    # 预构建 renderer（一次），相机在调用时传入以覆盖
    cams_dummy = FoVPerspectiveCameras(
        device=device,
        R=torch.eye(3, device=device, dtype=dtype).unsqueeze(0),
        T=torch.zeros(1, 3, device=device, dtype=dtype),
        fov=fov,
        degrees=True,
        znear=znear,
        zfar=zfar,
        aspect_ratio=float(W) / float(H),
    )
    raster = MeshRasterizer(
        cameras=cams_dummy,
        raster_settings=RasterizationSettings(
            image_size=(H, W),
            faces_per_pixel=1,
            cull_backfaces=False,
        ),
    )
    shader = HardPhongShader(device=device, cameras=cams_dummy)
    renderer = MeshRenderer(rasterizer=raster, shader=shader)

    # 相机位姿（camera->world），形状 (N,4,4)
    poses_cw = create_circular_camera_poses(num_views, radius, axis)  # (N,4,4)

    images, depths = [], []
    for i in range(num_views):
        # 取第 i 个位姿并转 world->camera
        pose = poses_cw[i]
        R_cw = pose[:3, :3]
        t_cw = pose[:3, 3]
        R_wc = R_cw.transpose(0, 1)
        T_wc = -R_wc @ t_cw

        cameras = FoVPerspectiveCameras(
            device=device,
            R=R_wc.unsqueeze(0),
            T=T_wc.unsqueeze(0),
            fov=fov,
            degrees=True,
            znear=znear,
            zfar=zfar,
            aspect_ratio=float(W) / float(H),
        )

        # 灯光：与原逻辑一致，若提供强度则把方向光与相机对齐，否则无光
        if light_intensity is None:
            lights = None  # 在 render 内部会被置为零辐照
        else:
            cam_pos = t_cw  # camera->world 的平移即相机在世界的位置
            v = -cam_pos / torch.clamp(cam_pos.norm(), min=torch.finfo(dtype).eps)
            diff = float(light_intensity)
            lights = DirectionalLights(
                device=device,
                direction=v.view(1, 3),
                ambient_color=[[0.0, 0.0, 0.0]],
                diffuse_color=[[diff, diff, diff]],
                specular_color=[[0.0, 0.0, 0.0]],
            )

        color_i, depth_i = render(
            meshes=mesh,
            renderer=renderer,
            cameras=cameras,
            lights=lights,
            normalize_depth=normalize_depth,
            return_type=return_type,
        )
        images.append(color_i)
        depths.append(depth_i)

    if return_depth:
        return images, depths
    return images


@torch.no_grad()
def render_normal_views_around_mesh(
    mesh: Meshes,
    num_views: int = 36,
    radius: float = 3.5,
    axis: torch.Tensor = torch.tensor([0.0, 1.0, 0.0]),
    image_size: Tuple[int, int] = (512, 512),  # (H, W)
    fov: float = 40.0,
    light_intensity: Optional[float] = 5.0,
    znear: float = 0.1,
    zfar: float = 10.0,
    normalize_depth: bool = False,
    flags: int = 0,  # 占位，不使用
    return_depth: bool = False,
    return_type: str = "pil",  # "pil" | "ndarray"
) -> Union[List[Image.Image], List[np.ndarray], Tuple[List[Image.Image], List[Image.Image]], Tuple[List[np.ndarray], List[np.ndarray]]]:
    if not isinstance(mesh, Meshes):
        raise ValueError("mesh 必须是 pytorch3d.structures.Meshes")
    if len(mesh) != 1:
        raise ValueError("仅支持 batch=1")

    device = mesh.device
    dtype = mesh.verts_padded().dtype

    # 顶点法线映射到颜色 [0,1]，作为顶点纹理
    normals_packed = mesh.verts_normals_packed()  # (V,3)
    colors_packed = ((normals_packed + 1.0) * 0.5).clamp(0, 1)  # (V,3)
    colors = colors_packed.unsqueeze(0)  # (1,V,3)
    tex = TexturesVertex(verts_features=colors.to(device=device, dtype=dtype))
    colored_mesh = Meshes(verts=mesh.verts_list(), faces=mesh.faces_list(), textures=tex).to(device)

    # 直接复用多视图渲染
    return render_views_around_mesh(
        colored_mesh,
        num_views=num_views,
        radius=radius,
        axis=axis,
        image_size=image_size,
        fov=fov,
        light_intensity=light_intensity,
        znear=znear,
        zfar=zfar,
        normalize_depth=normalize_depth,
        flags=flags,
        return_depth=return_depth,
        return_type=return_type,
    )


def export_renderings(
    images: List[Image.Image],
    export_path: str,
    fps: int = 36,
    loop: int = 0,
):
    export_type = export_path.split(".")[-1]
    if export_type == "mp4":
        export_to_video(
            images,
            export_path,
            fps=fps,
        )
    elif export_type == "gif":
        duration = 1000 / fps
        images[0].save(export_path, save_all=True, append_images=images[1:], duration=duration, loop=loop)
    else:
        raise ValueError(f"Unknown export type: {export_type}")


def make_grid_for_images_or_videos(
    images_or_videos: Union[List[Image.Image], List[List[Image.Image]]],
    nrow: int = 4,
    padding: int = 0,
    pad_value: int = 0,
    image_size: tuple = (512, 512),
    return_type: Literal["pil", "ndarray"] = "pil",
) -> Union[Image.Image, List[Image.Image], np.ndarray]:
    if isinstance(images_or_videos[0], Image.Image):
        images = [np.array(image.resize(image_size).convert("RGB")) for image in images_or_videos]
        images = np.stack(images, axis=0).transpose(0, 3, 1, 2)  # [N, C, H, W]
        images = torch.from_numpy(images)
        image_grid = make_grid(images, nrow=nrow, padding=padding, pad_value=pad_value, normalize=False)  # [C, H', W']
        image_grid = image_grid.cpu().numpy()
        if return_type == "pil":
            image_grid = Image.fromarray(image_grid.transpose(1, 2, 0))
        return image_grid
    elif isinstance(images_or_videos[0], list) and isinstance(images_or_videos[0][0], Image.Image):
        image_grids = []
        for i in range(len(images_or_videos[0])):
            images = [video[i] for video in images_or_videos]
            image_grid = make_grid_for_images_or_videos(images, nrow=nrow, padding=padding, return_type=return_type)
            image_grids.append(image_grid)
        if return_type == "ndarray":
            image_grids = np.stack(image_grids, axis=0)
        return image_grids
    else:
        raise ValueError(f"Unknown input type: {type(images_or_videos[0])}")
