#!/usr/bin/env python3
import sys
import os
import json
import argparse
import logging
import hashlib
from pathlib import Path
import numpy as np
from PIL import Image

import numpy as np  # 若下游需要，保留
import trimesh
from src.utils.data_utils import normalize_mesh
from src.utils.render_utils import render_single_view


REQUIRED_FILES = ["rendering.png"]

ALLOWED_MODES = {"L", "RGB", "RGBA", "F"}  # uint8 与 float32 保持不动


def normalize_texture_pil(im: Image.Image):
    if not isinstance(im, Image.Image):
        return im
    m = im.mode
    if m in ALLOWED_MODES:
        return im
    if m == "1":  # 1bit -> 8bit 灰度
        return im.convert("L")
    if m == "P":  # 调色板 -> RGBA
        return im.convert("RGBA")
    if m == "LA":  # 灰度+alpha -> RGBA
        return im.convert("RGBA")
    if m in {"CMYK", "YCbCr", "HSV"}:  # 这些已是 uint8，但通道不兼容 -> RGB
        return im.convert("RGB")
    if m in {"I;16", "I;16B", "I;16L", "I"}:  # 16/32 位整型 -> 8bit 灰度
        arr = np.array(im, dtype=np.uint32)
        arr8 = (arr >> 8).astype(np.uint8)  # 不做拉伸，仅丢高 8 位
        return Image.fromarray(arr8, mode="L")
    # 兜底
    return im.convert("RGB")


def coerce_trimesh_textures_pil(tm):
    vis = getattr(tm, "visual", None)
    if vis is None:
        return
    mats = []
    if getattr(vis, "material", None) is not None:
        mats.append(vis.material)
    if getattr(vis, "materials", None):
        mats.extend(list(vis.materials))

    fields = (
        "image",  # SimpleMaterial
        "baseColorTexture",
        "metallicRoughnessTexture",
        "normalTexture",
        "occlusionTexture",
        "emissiveTexture",
        "diffuseTexture",
        "specularGlossinessTexture",
    )
    for m in mats:
        for f in fields:
            if hasattr(m, f):
                tex = getattr(m, f)
                setattr(m, f, normalize_texture_pil(tex))


def setup_logging():
    h = logging.StreamHandler(stream=sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(h)
    root.setLevel(logging.INFO)


def parse_size(s: str):
    # 形如 2048x2048 或 2048,2048 或 2048 2048
    for sep in ("x", "X", ",", " "):
        if sep in s:
            a, b = s.split(sep)
            return int(a), int(b)
    v = int(s)
    return v, v


def sha1_shard(relpath: str, num_shards: int) -> int:
    h = hashlib.sha1(relpath.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") % num_shards


def need_skip(out_dir: Path, ignore_existing: bool) -> bool:
    if not ignore_existing:
        return False
    return all((out_dir / f).exists() for f in REQUIRED_FILES)


def process_one(src_path: Path, out_root: Path, radius: float, image_size, light_intensity: float, num_env_lights: int):
    stem = src_path.stem
    out_dir = out_root / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    mesh = normalize_mesh(trimesh.load(src_path.as_posix(), process=False)).to_geometry()
    img = render_single_view(
        mesh,
        radius=radius,
        image_size=image_size,
        light_intensity=light_intensity,
        num_env_lights=num_env_lights,
        return_type="pil",
    )
    img.save(out_dir / "rendering.png")
    # 可选保存渲染配置，便于追溯
    with open(out_dir / "render_cfg.json", "w") as f:
        json.dump(dict(radius=radius, image_size=list(image_size), light_intensity=light_intensity, num_env_lights=num_env_lights, src=str(src_path)), f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src_dir", type=str, required=True)
    parser.add_argument("--tgt_dir", type=str, required=True)
    parser.add_argument("--num_shards", type=int, default=1)
    parser.add_argument("--shard_index", type=int, default=0)
    parser.add_argument("--ignore_existing", action="store_true")
    parser.add_argument("--ext", type=str, default=".glb")

    # 渲染参数
    parser.add_argument("--radius", type=float, default=4.0)
    parser.add_argument("--image_size", type=str, default="2048x2048")
    parser.add_argument("--light_intensity", type=float, default=2.5)
    parser.add_argument("--num_env_lights", type=int, default=36)

    args = parser.parse_args()
    setup_logging()

    src_dir = Path(args.src_dir).resolve()
    tgt_dir = Path(args.tgt_dir).resolve()
    if not src_dir.exists():
        logging.error("src_dir 不存在: %s", src_dir)
        sys.exit(1)
    if args.num_shards <= 0 or not (0 <= args.shard_index < args.num_shards):
        logging.error("分片参数非法: num_shards=%d shard_index=%d", args.num_shards, args.shard_index)
        sys.exit(1)
    tgt_dir.mkdir(parents=True, exist_ok=True)

    img_size = parse_size(args.image_size)
    ext = args.ext.lower()

    files = [p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() == ext]
    files.sort()
    if not files:
        logging.info("未发现 %s 文件 于 %s", ext, src_dir)
        return

    selected = []
    for p in files:
        rel = p.relative_to(src_dir).as_posix()
        if sha1_shard(rel, args.num_shards) == args.shard_index:
            selected.append(p)

    logging.info("总计 %d 个文件，本分片 %d 个 (index=%d/%d)", len(files), len(selected), args.shard_index, args.num_shards)

    ok = 0
    skipped = 0
    failed = 0
    for i, sp in enumerate(selected, 1):
        out_dir = tgt_dir / sp.stem
        if need_skip(out_dir, args.ignore_existing):
            skipped += 1
            logging.info("[%d/%d] 跳过已存在: %s", i, len(selected), sp)
            continue
        try:
            logging.info("[%d/%d] 渲染: %s", i, len(selected), sp)
            process_one(
                sp,
                tgt_dir,
                radius=args.radius,
                image_size=img_size,
                light_intensity=args.light_intensity,
                num_env_lights=args.num_env_lights,
            )
            ok += 1
            logging.info("完成 -> %s", out_dir)
        except Exception as e:
            failed += 1
            logging.error("失败: %s | %s", sp, repr(e))

    logging.info("统计 | 成功: %d 跳过: %d 失败: %d", ok, skipped, failed)


if __name__ == "__main__":
    main()
