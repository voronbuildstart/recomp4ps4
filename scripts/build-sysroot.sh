#!/usr/bin/env bash
# PS4 sysroot in the right order: libc-overlay → libc++/libc++abi → libdolphinps4_rt.a → ucontext overlay.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TS="$HERE/../projects/hm64-ps4/toolchain"
export PS4_BUILD_ROOT="${1:-${PS4_BUILD_ROOT:-$HOME/ps4-build}}"
export PS4_SYSROOT="$PS4_BUILD_ROOT/sysroot"

echo "==> prepare-sysroot (libc-overlay)"
bash "$TS/prepare-sysroot.sh"
echo "==> build-libcxx (libc++ 21)"
bash "$TS/build-libcxx.sh"
echo "==> build-runtime (libdolphinps4_rt.a)"
bash "$TS/build-runtime.sh"
echo "==> ucontext-overlay (M33 fixes)"
bash "$TS/ucontext-overlay.sh"
echo "sysroot ready: $PS4_SYSROOT"
ls -la "$PS4_SYSROOT/lib/libc++.a" "$PS4_SYSROOT/lib/libdolphinps4_rt.a"
