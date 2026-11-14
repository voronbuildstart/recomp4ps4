#!/usr/bin/env bash
# Clone libdrm headers only (needed by Mesa's meson configure).
set -euo pipefail
ROOT="${1:-$HOME/ps4-build}"
PATCHED="$ROOT/src/libdrm"

mkdir -p "$ROOT/src"
if [ -d "$PATCHED" ]; then
    echo "libdrm already present: $PATCHED"
    exit 0
fi
echo "cloning libdrm headers..."
git clone --depth 1 --branch libdrm-2.4.131 https://gitlab.freedesktop.org/mesa/drm.git "$PATCHED"
echo "libdrm headers present."
