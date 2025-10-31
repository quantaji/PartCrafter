#!/usr/bin/env python3
import os
import sys
import json
import argparse
import logging
import hashlib
from pathlib import Path

import numpy as np
import trimesh

from src.utils.data_utils import scene_to_parts, mesh_to_surface, normalize_mesh


REQUIRED_FILES = ["points.npy", "num_parts.json"]


def setup_logging():
    handler = logging.StreamHandler(stream=sys.stdout)
    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def sha1_shard(relpath: str, num_shards: int) -> int:
    h = hashlib.sha1(relpath.encode("utf-8")).digest()
    # use first 8 bytes for a stable 64-bit integer
    v = int.from_bytes(h[:8], byteorder="big", signed=False)
    return v % num_shards


def need_skip(target_dir: Path, ignore_existing: bool) -> bool:
    if not ignore_existing:
        return False
    for name in REQUIRED_FILES:
        if not (target_dir / name).exists():
            return False
    return True


def filter_mesh(obj):
    import trimesh

    if isinstance(obj, trimesh.Trimesh):
        return obj.copy()
    if isinstance(obj, trimesh.Scene):
        sc = trimesh.Scene()
        for name, g in obj.geometry.items():
            if isinstance(g, trimesh.Trimesh):
                sc.add_geometry(g.copy(), node_name=name)
        return sc
    return trimesh.Scene()


def process_one(src_path: Path, out_root: Path):
    mesh_name = src_path.stem
    out_dir = out_root / mesh_name
    out_dir.mkdir(parents=True, exist_ok=True)

    config = {"num_parts": 0}

    # load and normalize
    mesh = trimesh.load(src_path.as_posix(), process=False)
    mesh = normalize_mesh(mesh)

    # filter out non-mesh geometry
    mesh = filter_mesh(mesh)

    # parts
    # assume normalize_mesh returns a trimesh.Scene when input is multi-geometry
    # len(mesh.geometry) on Scene
    config["num_parts"] = len(mesh.geometry)
    if 1 < config["num_parts"] <= 16:
        parts = scene_to_parts(mesh, return_type="point", normalize=False)
    else:
        parts = []

    # object surface points
    mesh_geo = mesh.to_geometry()
    obj = mesh_to_surface(mesh_geo, return_dict=True)

    datas = {"object": obj, "parts": parts}

    # save points
    np.save(out_dir / "points.npy", datas)
    # save config
    with open(out_dir / "num_parts.json", "w") as f:
        json.dump(config, f, indent=4)

    return out_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src_dir", type=str, required=True)
    parser.add_argument("--tgt_dir", type=str, required=True)
    parser.add_argument("--num_shards", type=int, default=1)
    parser.add_argument("--shard_index", type=int, default=0)
    parser.add_argument("--ignore_existing", action="store_true")
    parser.add_argument("--ext", type=str, default=".glb")
    args = parser.parse_args()

    setup_logging()

    src_dir = Path(args.src_dir).resolve()
    tgt_dir = Path(args.tgt_dir).resolve()
    ext = args.ext.lower()

    if not src_dir.exists():
        logging.error("src_dir %s 不存在", src_dir)
        sys.exit(1)

    if args.num_shards <= 0:
        logging.error("num_shards 必须大于 0")
        sys.exit(1)
    if not (0 <= args.shard_index < args.num_shards):
        logging.error("shard_index 取值范围为 [0, %d)", args.num_shards)
        sys.exit(1)

    tgt_dir.mkdir(parents=True, exist_ok=True)

    # collect files recursively
    files = [p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() == ext]
    files.sort()

    if not files:
        logging.info("未找到任何 %s 文件于 %s", ext, src_dir)
        return

    # shard by relative path to src_dir
    selected = []
    for p in files:
        rel = p.relative_to(src_dir).as_posix()
        shard = sha1_shard(rel, args.num_shards)
        if shard == args.shard_index:
            selected.append(p)

    logging.info("总计发现 %d 个文件，当前分片选择 %d 个 (index=%d/%d)", len(files), len(selected), args.shard_index, args.num_shards)

    processed = 0
    skipped_existing = 0
    failed = 0

    for idx, path in enumerate(selected, 1):
        mesh_name = path.stem
        out_dir = tgt_dir / mesh_name

        if need_skip(out_dir, args.ignore_existing):
            skipped_existing += 1
            logging.info("[%d/%d] 跳过已存在: %s", idx, len(selected), mesh_name)
            continue

        try:
            logging.info("[%d/%d] 处理: %s", idx, len(selected), path)
            out_dir = process_one(path, tgt_dir)
            processed += 1
            logging.info("完成 -> %s", out_dir)
        except Exception as e:
            failed += 1
            logging.error("失败: %s | %s", path, repr(e))

    logging.info("统计 | 成功: %d 跳过: %d 失败: %d", processed, skipped_existing, failed)


if __name__ == "__main__":
    main()
