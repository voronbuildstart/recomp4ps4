#!/usr/bin/env bash
# One-command fresh-machine setup: install host deps, OpenOrbis SDK, Mesa, netfs libs, sysroot.
# Usage: bash scripts/setup-all.sh [build-root]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$HOME/ps4-build}"
export PS4_BUILD_ROOT="$ROOT"

echo "==> 1. host packages"
bash "$HERE/setup-deps.sh"

echo "==> 2. OpenOrbis PS4 toolchain (Pacbrew prebuilt, ~70 MB)"
bash "$HERE/setup-openorbis.sh"

echo "==> 3. PS4 sysroot (libc++ 21, ~10 min)"
bash "$HERE/build-sysroot.sh" "$ROOT"

echo "==> 4. Mesa RADV: clone + patch + cross-file build (~15 min)"
bash "$HERE/clone-libdrm.sh" "$ROOT"
bash "$HERE/setup-mesa.sh" "$ROOT"
bash "$HERE/build-mesa.sh" "$ROOT"

echo "==> 5. SDL2 + FreeType into sysroot (hm64-ps4's build-deps)"
export PS4_BUILD_ROOT="$ROOT"
bash "$HERE/../projects/hm64-ps4/scripts/build-deps.sh"

echo "==> 6. libnfs + libsmb2 (network shares)"
bash "$HERE/build-netfs.sh" "$ROOT"

echo
echo "ALL DEPS INSTALLED. Next: run the game's build:"
echo "  python3 r4p.py ps4 hm64 --build   # or mp3"
echo "  (the recomp clone + ROM verification happen there)"
