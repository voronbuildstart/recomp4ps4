#!/usr/bin/env bash
# Install host build dependencies via apt (Ubuntu/Debian). Skips already-installed packages.
# Dry run: setup-deps.sh dry — prints what's missing.
set -euo pipefail

pkgs=(
    clang-21 clang++-21 lld-21 llvm-21 \
    cmake ninja-build make git curl zstd pkg-config \
    python3 python3-pip python3-venv python3-mako python3-yaml \
    mesa-vulkan-drivers libgl-dev libvulkan-dev
)

missing=()
for p in "${pkgs[@]}"; do
    # Ubuntu's clang++-21 is a virtual package provided by clang-21; accept either.
    if [ "$p" = "clang++-21" ]; then
        if ! dpkg-query -W -f='${Status}' clang-21 2>/dev/null | grep -q 'install ok installed' 2>/dev/null && ! command -v clang++-21 >/dev/null 2>&1; then
            missing+=("$p")
        fi
        continue
    fi
    if ! dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q 'install ok installed'; then
        missing+=("$p")
    fi
done
if [ "${1:-}" = "dry" ] || [ "${#missing[@]}" -eq 0 ]; then
    if [ "${#missing[@]}" -eq 0 ]; then
        echo "all host packages installed."
    else
        echo "apt-get install -y ${missing[*]}"
    fi
    exit 0
fi
echo "missing packages: ${missing[*]}"

if [ "$(id -u)" -eq 0 ]; then
    apt-get update
    apt-get install -y "${missing[@]}"
elif command -v pkexec >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
    echo "prompting for authentication..."
    pkexec apt-get update
    pkexec apt-get install -y "${missing[@]}"
elif command -v sudo >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y "${missing[@]}"
else
    echo "need root or sudo/pkexec to install: ${missing[*]}" >&2
    echo "please run: sudo apt-get install -y ${missing[*]}" >&2
    exit 1
fi
echo "done."
