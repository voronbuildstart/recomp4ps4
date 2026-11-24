#!/usr/bin/env bash
# Configure GauntletRecomp's host (GauntletRecompiled) for the PS4: RT64 on RADV (GNM) through the
# port's VideoOut WSI, Gauntlet's own menus, SDL2/FreeType from the sysroot. Run through ~/gauntlet
# (no space in the path).
#   configure-gauntlet.sh [extra cmake args...]
# pthreads are in libkernel, but CMake's probe programs don't link: FindThreads is told.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/ps4-env.sh"
SRC="${GAUNTLET_SRC:-$PS4_BUILD_ROOT/src/GauntletLegendsRecomp}"
BUILD="$PS4_BUILD_ROOT/build/gauntlet"
export PS4_SYSROOT="$PS4_BUILD_ROOT/sysroot"
export PKG_CONFIG_LIBDIR="$PS4_SYSROOT/lib/pkgconfig"
unset PKG_CONFIG_PATH
ps4_cmake -S "$SRC" -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$HERE/../toolchain/ps4-gauntlet.cmake" \
    "-DCMAKE_PROJECT_GauntletRecompiled_INCLUDE=$HERE/../toolchain/ps4-love-style.cmake" \
    -DGAUNTLET_PS4_DIR="$(cd "$HERE/../ps4" && pwd)" \
    -DPS4_PAID="${PS4_PAID:-0x3800000000000035}" \
    -DPS4_MESA_BUILD="$PS4_BUILD_ROOT/build/mesa" \
    -DPS4_SYSROOT="$PS4_SYSROOT" \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DPLUTOVG_BUILD_EXAMPLES=OFF \
    -DSDL2_DIR="$PS4_SYSROOT/lib/cmake/SDL2" \
    -DCMAKE_HAVE_LIBC_PTHREAD=1 -DCMAKE_THREAD_LIBS_INIT= -DThreads_FOUND=TRUE \
    -DBUILD_TESTING=OFF \
    "$@"
