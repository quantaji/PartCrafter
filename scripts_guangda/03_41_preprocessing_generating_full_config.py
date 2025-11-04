#!/usr/bin/env python3
import os
import json
import argparse
from pathlib import Path
from tqdm import tqdm

REQ_FILES = [
    "num_parts.json",
    "points.npy",
    # "render_cfg.json",
    "rendering_rmbg.png",
    "iou.json",
]

def parse_args():
    p = argparse.ArgumentParser(
        description="汇总所有数据集为单一 config。无采样，无拷贝。路径按 apptainer 扁平映射。"
    )
    p.add_argument("--dataset_name", action="append", required=True,
                   help="数据集名。可多次出现，与 --dataset_dir 成对")
    p.add_argument("--dataset_dir", action="append", required=True,
                   help="预处理根目录，子目录名为 uuid。可多次出现")
    p.add_argument("--glb_dir", action="append", required=True,
                   help="存放 <uuid>.glb 的根目录。可多次出现")
    p.add_argument("--apptainer_dir", required=True,
                   help="容器内根目录。各 dataset_dir 和 glb_dir 扁平挂载到其下一层")
    p.add_argument("--config_path", required=True,
                   help="输出 JSON 路径，如 /path/to/data_configs_all.json")
    return p.parse_args()

def ensure_pairs(names, dirs):
    if len(names) != len(dirs):
        raise ValueError("--dataset_name 与 --dataset_dir 次数不一致")

def list_uuids(dataset_dir: Path):
    if not dataset_dir.exists():
        return []
    return sorted([d.name for d in dataset_dir.iterdir() if d.is_dir()])

def find_glb(uuid: str, glb_dirs):
    fname = f"{uuid}.glb"
    for gd in glb_dirs:
        p = gd / fname
        if p.is_file():
            return p
    return None

def check_complete(sample_dir: Path, glb_path: Path ):
    if glb_path is None:
        return False
    for fn in REQ_FILES:
        if not (sample_dir / fn).is_file():
            return False
    return True

def read_num_parts(sample_dir: Path):
    try:
        with open(sample_dir / "num_parts.json", "r") as f:
            return int(json.load(f).get("num_parts", 0))
    except Exception:
        return 0

def read_iou(sample_dir: Path):
    mean = 0.0
    mx = 0.0
    try:
        with open(sample_dir / "iou.json", "r") as f:
            d = json.load(f)
        mean = float(d.get("iou_mean", 0.0))
        mx = float(d.get("iou_max", 0.0))
    except Exception:
        pass
    return mean, mx

def to_container_path(host_path: Path, root_host: Path, app_root: Path) -> str:
    # 映射：<apptainer_dir>/<basename(root_host)>/<relative_to_root_host>
    rel = host_path.resolve().relative_to(root_host.resolve())
    return str(app_root.joinpath(root_host.name, rel))

def main():
    args = parse_args()
    ensure_pairs(args.dataset_name, args.dataset_dir)

    app_root = Path(args.apptainer_dir).resolve()
    ds_pairs = [(n, Path(d).resolve()) for n, d in zip(args.dataset_name, args.dataset_dir)]
    glb_dirs = [Path(g).resolve() for g in args.glb_dir]

    items = []

    for ds_name, ds_root in tqdm(ds_pairs, desc="Datasets"):
        uuids = list_uuids(ds_root)
        for uid in tqdm(uuids, desc=f"{ds_name}", leave=False):
            sample_dir = ds_root / uid
            glb_src = find_glb(uid, glb_dirs)

            valid = check_complete(sample_dir, glb_src)
            num_parts = read_num_parts(sample_dir)
            iou_mean, iou_max = read_iou(sample_dir)

            # 扁平映射路径
            # dataset 内文件来自 ds_root
            points_p = sample_dir / "points.npy"
            img_p = sample_dir / "rendering_rmbg.png"
            # glb 来自命中的 glb_dir
            mesh_p = glb_src if glb_src is not None else None

            # 容器内绝对路径
            surface_path = to_container_path(points_p, ds_root, app_root) if points_p.is_file() else None
            image_path = to_container_path(img_p, ds_root, app_root) if img_p.is_file() else None
            mesh_path = (
                to_container_path(mesh_p, mesh_p.parent.parent if mesh_p else Path("/"), app_root)
                if mesh_p is not None else None
            )
            # 解释：mesh_p.parent 是 glb_dir，本行用其上级 parent.parent 写错了？更正如下：
            if mesh_p is not None:
                mesh_path = to_container_path(mesh_p, mesh_p.parent, app_root)

            item = {
                "dataset": ds_name,
                "file": f"{uid}.glb",
                # "folder": uid[:3],  # 分桶，取前 3 个字符
                "num_parts": int(num_parts),
                "valid": bool(valid),
                "mesh_path": mesh_path,
                "surface_path": surface_path,
                "image_path": image_path,
                "iou_mean": float(iou_mean),
                "iou_max": float(iou_max),
            }
            items.append(item)

    out = Path(args.config_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(items, f, indent=4)
    print(f"Wrote config: {out}")

if __name__ == "__main__":
    main()


# /usr/bin/python scripts_guangda/03_41_preprocessing_generating_full_config.py \
#   --dataset_name objaverse \
#   --dataset_dir /scratch/quanta/objaverse_partcrafter_preprocessed \
#   --glb_dir /scratch/quanta/objaverse_selected \
#   --dataset_name partverse \
#   --dataset_dir /scratch/quanta/partverse_partcrafter_preprocessed \
#   --glb_dir /scratch/quanta/partverse_selected \
#   --apptainer_dir /dataset \
#   --config_path ./datasets/data_configs_full_qinchan.json
