#!/usr/bin/env python3
import sys
import os
import json
import logging
import argparse
import hashlib
from pathlib import Path

import numpy as np
import trimesh

from src.utils.data_utils import normalize_mesh
from src.utils.metric_utils import compute_IoU_for_scene

EXT = ".glb"
OUTPUT_FILE = "iou.json"
REQUIRED_FILES = [OUTPUT_FILE]


def setup_logging():
    h = logging.StreamHandler(stream=sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                     "%Y-%m-%d %H:%M:%S"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(h)
    root.setLevel(logging.INFO)


def sha1_shard(relpath: str, num_shards: int) -> int:
    v = int.from_bytes(hashlib.sha1(relpath.encode("utf-8")).digest()[:8], "big")
    return v % num_shards


def need_skip(out_dir: Path, ignore_existing: bool) -> bool:
    if not ignore_existing:
        return False
    for f in REQUIRED_FILES:
        if not (out_dir / f).exists():
            return False
    return True


def process_one(src_glb: Path, out_root: Path):
    mesh_name = src_glb.stem
    out_dir = out_root / mesh_name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / OUTPUT_FILE

    cfg = {
        "iou_mean": 0.0,
        "iou_max": 0.0,
        "iou_list": [],
    }

    mesh = normalize_mesh(trimesh.load(src_glb.as_posix(), process=False))
    try:
        iou_list = compute_IoU_for_scene(mesh, return_type="iou_list")
        iou_list = list(map(float, iou_list)) if iou_list is not None else []
        cfg["iou_list"] = iou_list
        if iou_list:
            cfg["iou_mean"] = float(np.mean(iou_list))
            cfg["iou_max"] = float(np.max(iou_list))
    except Exception as e:
        logging.error("IoU 计算失败: %s | %r", src_glb, e)

    with open(out_json, "w") as f:
        json.dump(cfg, f, indent=2)

    return out_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src_dir", type=str, required=True)
    parser.add_argument("--tgt_dir", type=str, required=True)
    parser.add_argument("--num_shards", type=int, default=1)
    parser.add_argument("--shard_index", type=int, default=0)
    parser.add_argument("--ignore_existing", action="store_true")
    args = parser.parse_args()

    setup_logging()

    src_root = Path(args.src_dir).resolve()
    tgt_root = Path(args.tgt_dir).resolve()
    if not src_root.exists():
        logging.error("src_dir 不存在: %s", src_root)
        sys.exit(1)
    tgt_root.mkdir(parents=True, exist_ok=True)

    if args.num_shards <= 0 or not (0 <= args.shard_index < args.num_shards):
        logging.error("分片参数非法: num_shards=%d shard_index=%d",
                      args.num_shards, args.shard_index)
        sys.exit(1)

    files = [p for p in src_root.rglob("*") if p.is_file() and p.suffix.lower() == EXT]
    files.sort()
    if not files:
        logging.info("未找到任何 %s 文件于 %s", EXT, src_root)
        return

    selected = []
    for p in files:
        rel = p.relative_to(src_root).as_posix()
        if sha1_shard(rel, args.num_shards) == args.shard_index:
            selected.append(p)

    logging.info("总计 %d 个 glb，本分片 %d 个 (index=%d/%d)",
                 len(files), len(selected), args.shard_index, args.num_shards)

    processed = 0
    skipped = 0
    failed = 0

    for i, glb in enumerate(selected, 1):
        name = glb.stem
        out_dir = tgt_root / name

        if need_skip(out_dir, args.ignore_existing):
            skipped += 1
            logging.info("[%d/%d] 跳过已存在: %s", i, len(selected), out_dir / OUTPUT_FILE)
            continue

        try:
            logging.info("[%d/%d] 处理: %s", i, len(selected), glb)
            out_dir = process_one(glb, tgt_root)
            processed += 1
            logging.info("完成 -> %s", out_dir / OUTPUT_FILE)
        except Exception as e:
            failed += 1
            logging.error("失败: %s | %r", glb, e)

    logging.info("统计 | 成功: %d 跳过: %d 失败: %d", processed, skipped, failed)


if __name__ == "__main__":
    main()
