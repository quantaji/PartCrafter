#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import trimesh


def load_mesh_as_single_trimesh(path: Path) -> trimesh.Trimesh:
    """
    读取一个glb文件
    该glb只包含一个geometry
    返回一个Trimesh对象
    force='mesh'可以把单个scene里的唯一mesh和它的transform烘进去
    """
    mesh = trimesh.load(path, force='mesh')
    if isinstance(mesh, trimesh.Scene):
        # 理论上不会到这里. 用户保证单geometry
        raise RuntimeError(f"{path} still loaded as Scene, not single mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError(f"{path} did not load as Trimesh")
    return mesh


def merge_meshes_to_scene(mesh_list):
    """
    给一组Trimesh对象
    放进同一个trimesh.Scene
    """
    scene = trimesh.Scene()
    for i, mesh in enumerate(mesh_list):
        scene.add_geometry(mesh, node_name=f"part_{i}")
    return scene


def export_scene_to_glb(scene: trimesh.Scene, out_path: Path):
    """
    把scene导出为glb
    """
    out_bytes = scene.export(file_type="glb")
    out_path.write_bytes(out_bytes)


def process_one_id(obj_id: str, src_root: Path, tgt_root: Path):
    """
    obj_id 是形如 "strid"
    src_root/strid/ 里面有 0.glb 1.glb ...
    合并后写到 tgt_root/strid.glb
    """
    folder = src_root / obj_id
    out_file = tgt_root / f"{obj_id}.glb"

    # 收集该目录下的 *.glb 按数字排序
    glb_files = sorted(
        folder.glob("*.glb"),
        key=lambda p: int(p.stem)
    )

    # 读进来
    meshes = []
    for f in glb_files:
        mesh = load_mesh_as_single_trimesh(f)
        meshes.append(mesh)

    # 合并
    scene = merge_meshes_to_scene(meshes)

    # 导出
    export_scene_to_glb(scene, out_file)

    # log
    print(f"[OK] {obj_id} -> {out_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Merge numbered GLB parts per ID into one GLB using trimesh"
    )
    parser.add_argument(
        "--json",
        required=True,
        help="path to json file that stores a list[str] of folder IDs"
    )
    parser.add_argument(
        "--srcdir",
        required=True,
        help="root directory that contains per-ID subfolders"
    )
    parser.add_argument(
        "--tgtdir",
        required=True,
        help="output directory. merged files will be written here as <id>.glb"
    )

    args = parser.parse_args()

    json_path = Path(args.json)
    src_root = Path(args.srcdir)
    tgt_root = Path(args.tgtdir)

    tgt_root.mkdir(parents=True, exist_ok=True)

    # 读取id列表
    with json_path.open("r", encoding="utf-8") as f:
        id_list = json.load(f)

    # 假定 json 是 ["id1","id2",...]
    for obj_id in id_list:
        process_one_id(obj_id, src_root, tgt_root)


if __name__ == "__main__":
    main()
