#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path
import sys
from collections import defaultdict

def load_stems(json_path: Path):
    if not json_path.is_file():
        sys.exit(f"json文件不存在: {json_path}")
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        sys.exit(f"读取json失败: {e}")

    if not isinstance(data, list):
        sys.exit('json内容必须是list 例如 ["IMG_1234", "DSC_9999"]')

    stems = []
    for item in data:
        if isinstance(item, str):
            stems.append(item)
        else:
            sys.exit("列表里必须都是字符串")
    return stems

def index_srcdir(srcdir: Path):
    """
    建立映射:
    key: 去掉扩展名后的stem
    value: [Path(...), Path(...)]
    不判断文件或目录
    不递归
    不调用stat
    """
    mapping = defaultdict(list)
    for p in srcdir.iterdir():
        # Path.iterdir 本身不会stat
        mapping[p.stem].append(p)
    return mapping

def check_mode(target_stems, stem_to_paths):
    exist_stems = []
    missing_stems = []

    for stem in target_stems:
        if stem in stem_to_paths and stem_to_paths[stem]:
            exist_stems.append(stem)
        else:
            missing_stems.append(stem)

    print(f"总共 {len(target_stems)} 个stem")
    print(f"找到 {len(exist_stems)} 个stem")
    print(f"缺失 {len(missing_stems)} 个stem")

    if exist_stems:
        print("\nstem已找到对应条目:")
        for s in exist_stems:
            names = [p.name for p in stem_to_paths[s]]
            print(f"{s} -> {names}")

    if missing_stems:
        print("\n缺失stem:", file=sys.stderr)
        for s in missing_stems:
            print(s, file=sys.stderr)

def safe_copy_any(src_path: Path, dst_path: Path):
    """
    先按普通文件复制
    如果报IsADirectoryError则当成目录递归复制
    如果目标目录已存在则允许合并
    """
    try:
        shutil.copy2(src_path, dst_path)
    except IsADirectoryError:
        # Python 3.8+ 支持 dirs_exist_ok
        shutil.copytree(src_path, dst_path, dirs_exist_ok=True)

def copy_mode(target_stems, stem_to_paths, dstdir: Path, strict: bool):
    dstdir.mkdir(parents=True, exist_ok=True)

    copied_items = 0
    missing_stems = []

    for stem in target_stems:
        paths = stem_to_paths.get(stem, [])
        if not paths:
            print(f"警告: 未找到 {stem}", file=sys.stderr)
            missing_stems.append(stem)
            continue

        for src_obj in paths:
            dst_obj = dstdir / src_obj.name
            try:
                safe_copy_any(src_obj, dst_obj)
                copied_items += 1
            except Exception as e:
                print(f"错误: 复制 {src_obj} -> {dst_obj} 失败: {e}", file=sys.stderr)

    print(f"复制完成 共复制 {copied_items} 个条目")
    if missing_stems:
        print(f"这些stem没有匹配到任何条目: {missing_stems}", file=sys.stderr)
        if strict:
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="根据不带扩展名的stem列表检查或复制 同名文件或目录都复制"
    )
    parser.add_argument("--json", required=True,
                        help='包含stem列表的json文件路径 例如 ["IMG_1234","P0001"]')
    parser.add_argument("--srcdir", required=True,
                        help="源目录 只扫描这一层 不递归 不做stat权限检查")
    parser.add_argument("--dstdir",
                        help="目标目录 只在copy模式需要")
    parser.add_argument("--mode",
                        choices=["check", "copy"],
                        default="check",
                        help="check只检查 copy会实际复制")
    parser.add_argument("--strict",
                        action="store_true",
                        help="copy模式下 如果有stem完全没找到 则返回非零退出码")
    args = parser.parse_args()

    srcdir = Path(args.srcdir)
    if not srcdir.is_dir():
        sys.exit(f"源目录不存在: {srcdir}")

    stems = load_stems(Path(args.json))
    stem_to_paths = index_srcdir(srcdir)

    if args.mode == "check":
        check_mode(stems, stem_to_paths)
        return

    if args.mode == "copy":
        if not args.dstdir:
            sys.exit("copy模式必须提供 --dstdir")
        dstdir = Path(args.dstdir)
        copy_mode(stems, stem_to_paths, dstdir, args.strict)
        return

if __name__ == "__main__":
    main()
