#!/usr/bin/env bash
set -euo pipefail

# 目标包名单，按需改
PKGS=(libegl1 libegl-mesa0 libgl1-mesa-dri libgbm1 libgles2 libwayland-egl1 libglx-mesa0)

# 只演练：DRYRUN=1 ./script.sh
DRYRUN=${DRYRUN:-0}

# 收集这些包安装的“文件或符号链接”（不含目录）
declare -a FILES=()
for p in "${PKGS[@]}"; do
  if dpkg -s "$p" >/dev/null 2>&1; then
    while IFS= read -r path; do
      [[ -z "${path:-}" ]] && continue
      # 只保留存在的常规文件或符号链接
      if [[ -f "$path" || -L "$path" ]]; then
        FILES+=("$path")
      fi
    done < <(dpkg -L "$p" 2>/dev/null || true)
  fi
done

# 去重
mapfile -t FILES < <(printf '%s\n' "${FILES[@]}" | sort -u)

echo "将处理文件/链接总数: ${#FILES[@]}"
if [[ "${#FILES[@]}" -eq 0 ]]; then
  echo "无可删对象"
  exit 0
fi

if [[ "$DRYRUN" -eq 1 ]]; then
  printf 'DRYRUN 列表:\n'
  printf '  %s\n' "${FILES[@]}"
  exit 0
fi

# 删除文件与符号链接（不动目录）
for f in "${FILES[@]}"; do
  rm -f -- "$f" 2>/dev/null || true
done

# 刷新动态链接缓存（如有）
ldconfig 2>/dev/null || true

# 验证：包仍在，但其列出的文件应不存在
echo "验证残留..."
left=0
for p in "${PKGS[@]}"; do
  if dpkg -s "$p" >/dev/null 2>&1; then
    while IFS= read -r path; do
      [[ -z "${path:-}" ]] && continue
      if [[ -f "$path" || -L "$path" ]]; then
        echo "残留文件: $path  (from $p)"
        left=$((left+1))
      fi
    done < <(dpkg -L "$p" 2>/dev/null || true)
  fi
done

if [[ "$left" -eq 0 ]]; then
  echo "验证通过：上述包的文件已清空（目录未动）。"
  exit 0
else
  echo "验证失败：仍有 $left 个残留文件。"
  exit 1
fi
