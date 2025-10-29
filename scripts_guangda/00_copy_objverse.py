#!/usr/bin/env python3
import argparse
import json
import shutil
from pathlib import Path
import sys


def load_list(json_path: Path):
    if not json_path.is_file():
        sys.exit(f"json文件不存在: {json_path}")
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        sys.exit(f"读取json失败: {e}")

    if not isinstance(data, list):
        sys.exit('json内容必须是list, 例如 ["a.jpg", "b.png"]')

    # 统一成字符串列表
    out = []
    for item in data:
        if isinstance(item, str):
            out.append(item)
        else:
            sys.exit("列表里必须都是字符串文件名")
    return out


def check_files(names, srcdir: Path):
    exist_list = []
    missing_list = []

    for name in names:
        p = srcdir / name
        if p.is_file():
            exist_list.append(name)
        else:
            missing_list.append(name)

    return exist_list, missing_list


def do_copy(names, srcdir: Path, dstdir: Path, strict: bool):
    dstdir.mkdir(parents=True, exist_ok=True)

    copied = 0
    missing = []

    for name in names:
        src_file = srcdir / name
        if src_file.is_file():
            dst_file = dstdir / src_file.name
            shutil.copy2(src_file, dst_file)
            copied += 1
        else:
            print(f"警告: 未找到 {src_file}", file=sys.stderr)
            missing.append(name)

    print(f"复制完成 复制了 {copied} 个文件")
    if missing:
        print(f"缺失 {len(missing)} 个文件", file=sys.stderr)
        if strict:
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="根据文件名列表检查或复制文件")
    parser.add_argument("--json", required=True, help="包含文件名列表的json文件路径")
    parser.add_argument("--srcdir", required=True, help="源目录")
    parser.add_argument("--dstdir", help="目标目录 只在copy模式需要")
    parser.add_argument("--mode", choices=["check", "copy"], default="check", help="check只检查存在性 copy会复制")
    parser.add_argument("--strict", action="store_true", help="copy模式下 如果有缺失则用非零退出码")
    args = parser.parse_args()

    json_path = Path(args.json)
    srcdir = Path(args.srcdir)

    if not srcdir.is_dir():
        sys.exit(f"源目录不存在: {srcdir}")

    names = load_list(json_path)

    if args.mode == "check":
        exist_list, missing_list = check_files(names, srcdir)
        print(f"总计 {len(names)} 个名字")
        print(f"存在 {len(exist_list)} 个文件")
        print(f"缺失 {len(missing_list)} 个文件")

        if exist_list:
            print("\n存在的文件名:")
            for n in exist_list:
                print(n)

        if missing_list:
            print("\n缺失的文件名:", file=sys.stderr)
            for n in missing_list:
                print(n, file=sys.stderr)

        # check模式不复制 不创建目标目录
        # 正常退出即可
        return

    # mode == copy
    if not args.dstdir:
        sys.exit("copy模式必须提供 --dstdir")
    dstdir = Path(args.dstdir)

    do_copy(names, srcdir, dstdir, args.strict)


if __name__ == "__main__":
    main()
