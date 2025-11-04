#!/usr/bin/env python3
import os
import json
import argparse
import random
import shutil
from pathlib import Path

REQ_FILES = [
    "num_parts.json",
    "points.npy",
    "rendering_rmbg.png",
    "iou.json",
]
# rendering.png 不是必须

def parse_args():
    p = argparse.ArgumentParser(
        description="采样各数据集 n 条，验证并拷贝到目标目录，生成测试用 config。"
    )
    p.add_argument("--dataset_name", action="append", required=True,
                   help="数据集名。可多次出现，对应同序号的 --dataset_dir 与 --n")
    p.add_argument("--dataset_dir", action="append", required=True,
                   help="该数据集的预处理根目录，子目录名为 uuid。可多次出现")
    p.add_argument("--n", action="append", type=int, required=False,
                   help="该数据集采样数量。可多次出现，缺省用默认值填充")
    p.add_argument("--glb_dir", action="append", required=True,
                   help="存放 <uuid>.glb 的根目录。可多次出现")
    p.add_argument("--tgt_dir", required=True, help="目标根目录，如 /xxx/test_data_root")
    p.add_argument("--apptainer_dir", required=True,
                   help="容器内根前缀。配置里绝对路径以此为前缀映射")
    p.add_argument("--seed", type=int, default=42, help="随机种子")
    p.add_argument("--default_n", type=int, default=16, help="未显式给出 --n 时的默认值")
    p.add_argument("--config_name", default="test_configs.json",
                   help="输出配置文件名，写入到 tgt_dir 根")
    return p.parse_args()

def assert_group_lengths(names, dirs, ns, default_n):
    if len(names) != len(dirs):
        raise ValueError("--dataset_name 与 --dataset_dir 次数不一致")
    # 标准化 ns 长度
    if ns is None:
        ns = []
    ns = list(ns)
    while len(ns) < len(names):
        ns.append(default_n)
    if len(ns) > len(names):
        # 多给了 n，也只取前 len(names) 个
        ns = ns[:len(names)]
    return ns

def list_uuids(dataset_dir: Path):
    # 一层子目录名为 uuid，只取目录
    if not dataset_dir.exists():
        return []
    return sorted([d.name for d in dataset_dir.iterdir() if d.is_dir()])

def find_glb(uuid: str, glb_dirs):
    fname = f"{uuid}.glb"
    for gd in glb_dirs:
        p = gd / fname
        if p.exists() and p.is_file():
            return p
    return None

def check_entry_complete(sample_dir: Path, glb_path: Path | None):
    ok = True
    missing = []
    for fn in REQ_FILES:
        fp = sample_dir / fn
        if not (fp.exists() and fp.is_file()):
            ok = False
            missing.append(fn)
    if glb_path is None:
        ok = False
        missing.append("<uuid>.glb")
    return ok, missing

def read_num_parts(sample_dir: Path):
    try:
        with open(sample_dir / "num_parts.json", "r") as f:
            data = json.load(f)
        return int(data.get("num_parts", 0))
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

def copy_existing(src: Path, dst: Path):
    if src.exists() and src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def host_to_container_path(host_path: Path, tgt_root: Path, apptainer_root: Path) -> str:
    # 将真实拷贝位置映射为容器内绝对路径：<apptainer_root>/<relative_to_tgt_root>
    rel = host_path.resolve().relative_to(tgt_root.resolve())
    return str(apptainer_root.joinpath(rel))

def main():
    args = parse_args()
    random.seed(args.seed)

    names = [str(x) for x in args.dataset_name]
    dirs = [Path(x) for x in args.dataset_dir]
    ns = assert_group_lengths(names, dirs, args.n, args.default_n)
    glb_dirs = [Path(x) for x in args.glb_dir]
    tgt_root = Path(args.tgt_dir).resolve()
    app_root = Path(args.apptainer_dir).resolve()

    tgt_root.mkdir(parents=True, exist_ok=True)

    all_items = []

    for name, ddir, k in zip(names, dirs, ns):
        uuids = list_uuids(ddir)
        if len(uuids) == 0:
            # 空数据集也写入空结果
            continue
        # 采样 k 条，不补齐
        sampled = random.sample(uuids, k if k <= len(uuids) else len(uuids))
        for idx, uid in enumerate(sampled):
            src_dir = ddir / uid
            dst_dir = tgt_root / name / uid

            # 发现 glb
            glb_src = find_glb(uid, glb_dirs)

            # 校验
            valid, _missing = check_entry_complete(src_dir, glb_src)

            # 拷贝现有文件
            for fn in set(REQ_FILES):  
                fp = src_dir / fn
                if fp.exists() and fp.is_file():
                    copy_existing(fp, dst_dir / fn)
            # 拷贝 glb
            if glb_src is not None:
                copy_existing(glb_src, dst_dir / f"{uid}.glb")

            # 读取元数据
            num_parts = read_num_parts(src_dir)
            iou_mean, iou_max = read_iou(src_dir)

            # 生成配置项：字段名尽量对齐你的示例
            item = {
                "dataset": name,
                "file": f"{uid}.glb",
                # 若需要分桶 folder，可按序号或自定义规则；这里给三位序号分桶示例
                # "folder": f"{idx:03d}",
                "num_parts": int(num_parts),
                "valid": bool(valid),
                "mesh_path": host_to_container_path(dst_dir / f"{uid}.glb", tgt_root, app_root)
                              if (dst_dir / f"{uid}.glb").exists() else None,
                "surface_path": host_to_container_path(dst_dir / "points.npy", tgt_root, app_root)
                                if (dst_dir / "points.npy").exists() else None,
                "image_path": host_to_container_path(dst_dir / "rendering_rmbg.png", tgt_root, app_root)
                              if (dst_dir / "rendering_rmbg.png").exists() else None,
                "iou_mean": float(iou_mean),
                "iou_max": float(iou_max),
            }
            all_items.append(item)

    # 写出配置
    out_path = args.config_name
    with open(out_path, "w") as f:
        json.dump(all_items, f, indent=4)
    print(f"Wrote config: {out_path}")

if __name__ == "__main__":
    main()



# generating apptainer test configs
# python scripts_guangda/03_40_preprocessing_test_dataset_config.py \
#   --dataset_name objaverse \
#   --dataset_dir /scratch/quanta/objaverse_partcrafter_preprocessed \
#   --glb_dir /scratch/quanta/objaverse_selected \
#   --dataset_name partverse \
#   --dataset_dir /scratch/quanta/partverse_partcrafter_preprocessed \
#   --glb_dir /scratch/quanta/partverse_selected \
#   --tgt_dir /scratch/quanta/partcrafter_test_dataset \
#   --apptainer_dir /dataset \
#   --seed 42 \
#   --config_name datasets/data_configs_test_apptainer.json
