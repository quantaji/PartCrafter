#!/usr/bin/env python3
import sys
import argparse
import logging
import hashlib
from pathlib import Path
import numpy as np

import torch
from src.utils.image_utils import prepare_image
from src.models.briarmbg import BriaRMBG

# 常量
RENDER_NAME = "rendering.png"
OUTPUT_NAME = "rendering_rmbg.png"
RMBG_WEIGHTS_DIR = "pretrained_weights/RMBG-1.4"
BG_WHITE = np.array([1.0, 1.0, 1.0])
DEVICE = "cuda:0"


def setup_logging():
    h = logging.StreamHandler(stream=sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                     "%Y-%m-%d %H:%M:%S"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(h)
    root.setLevel(logging.INFO)


def sha1_shard(text: str, num_shards: int) -> int:
    v = int.from_bytes(hashlib.sha1(text.encode("utf-8")).digest()[:8], "big")
    return v % num_shards


def find_data_dirs(src_root: Path):
    for p in src_root.rglob(RENDER_NAME):
        if p.is_file():
            yield p.parent


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

    # 收集数据点目录
    all_dirs = sorted(find_data_dirs(src_root))
    if not all_dirs:
        logging.info("未找到任何 %s", RENDER_NAME)
        return

    # 分片
    selected = []
    for d in all_dirs:
        rel = d.relative_to(src_root).as_posix()
        if sha1_shard(rel, args.num_shards) == args.shard_index:
            selected.append(d)

    logging.info("总计 %d 个数据点，本分片 %d 个 (index=%d/%d)",
                 len(all_dirs), len(selected), args.shard_index, args.num_shards)

    # 仅本地权重
    weights_path = Path(RMBG_WEIGHTS_DIR)
    if not weights_path.exists():
        logging.error("本地权重目录不存在: %s", weights_path)
        sys.exit(1)

    if not torch.cuda.is_available():
        logging.error("CUDA 不可用，但已固定 device=%s", DEVICE)
        sys.exit(1)

    torch.cuda.set_device(0)
    torch.set_grad_enabled(False)
    net = BriaRMBG.from_pretrained(str(weights_path)).to(DEVICE)
    net.eval()

    processed = 0
    skipped = 0
    failed = 0

    for i, d in enumerate(selected, 1):
        in_png = d / RENDER_NAME
        rel = d.relative_to(src_root)
        out_dir = tgt_root / rel
        out_png = out_dir / OUTPUT_NAME

        if args.ignore_existing and out_png.exists():
            skipped += 1
            logging.info("[%d/%d] 跳过已存在: %s", i, len(selected), out_png)
            continue

        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            logging.info("[%d/%d] 处理: %s -> %s", i, len(selected), in_png, out_png)
            img = prepare_image(str(in_png),
                                bg_color=BG_WHITE,
                                rmbg_net=net,
                                device=DEVICE)
            img.save(out_png)
            processed += 1
        except Exception as e:
            failed += 1
            logging.error("失败: %s | %r", d, e)

    logging.info("统计 | 成功: %d 跳过: %d 失败: %d", processed, skipped, failed)


if __name__ == "__main__":
    main()
