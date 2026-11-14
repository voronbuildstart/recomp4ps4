#!/usr/bin/env bash
# Shallow-clone Mesa 26.0.8 and apply the PS4 RADV patch.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$HOME/ps4-build}"
MESA_VER="mesa-26.0.8"
MESA_DIR="$ROOT/src/mesa"

mkdir -p "$ROOT/src"
if [ -d "$MESA_DIR" ]; then
    echo "mesa already present: $MESA_DIR"
    exit 0
fi
echo "cloning Mesa $MESA_VER (shallow, ~400 MB)..."
git clone --depth 1 --branch "$MESA_VER" \
    https://gitlab.freedesktop.org/mesa/mesa.git "$MESA_DIR"
echo "applying PS4 RADV patch from iHaiDeeZ/DolphinPS4..."
git -C "$MESA_DIR" apply "$HERE/../projects/hm64-ps4/patches/mesa/mesa-ps4.patch"
echo "Mesa patched."
