#!/usr/bin/env bash
set -euo pipefail

# 要检查的包名（可改）
PKGS=(libegl1 libegl-mesa0 libgl1-mesa-dri libgbm1 libgles2 libwayland-egl1 libglx-mesa0)

# 收集某个包的全部路径（含多架构变体），从 dpkg info 与 dpkg -L 双路获取
get_pkg_paths() {
  local pkg="$1"
  local -a paths=()

  # 1) 从 /var/lib/dpkg/info/*.list 读取（支持已删除未 purge 的情况）
  shopt -s nullglob
  local found=0
  for lf in /var/lib/dpkg/info/${pkg}*.list; do
    found=1
    # 逐行读取，忽略空行
    while IFS= read -r p; do
      [[ -n "${p:-}" ]] && paths+=("$p")
    done <"$lf"
  done
  shopt -u nullglob

  # 2) 若未找到且包处于安装状态，回退 dpkg -L
  if [[ $found -eq 0 ]] && dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q 'install ok installed'; then
    while IFS= read -r p; do
      [[ -n "${p:-}" ]] && paths+=("$p")
    done < <(dpkg -L "$pkg" 2>/dev/null || true)
  fi

  # 去重并输出
  if [[ ${#paths[@]} -gt 0 ]]; then
    printf '%s\n' "${paths[@]}" | sort -u
  fi
}

total_left=0
per_pkg_left=0

for pkg in "${PKGS[@]}"; do
  mapfile -t plist < <(get_pkg_paths "$pkg")
  if [[ ${#plist[@]} -eq 0 ]]; then
    echo "[OK] $pkg: 无清单（未安装或已 purge），视为通过"
    continue
  fi

  left=0
  declare -a leftovers=()
  for p in "${plist[@]}"; do
    # 只判定文件或符号链接是否存在；目录忽略
    if [[ -f "$p" || -L "$p" ]]; then
      leftovers+=("$p")
      left=$((left+1))
    fi
  done

  if [[ $left -eq 0 ]]; then
    echo "[OK] $pkg: 清单中的文件均已删除"
  else
    echo "[FAIL] $pkg: 残留文件数 $left"
    printf '  %s\n' "${leftovers[@]}"
  fi
  total_left=$((total_left+left))
done

if [[ $total_left -eq 0 ]]; then
  echo "全部通过：未发现残留文件"
  exit 0
else
  echo "发现残留总数：$total_left"
  exit 1
fi
