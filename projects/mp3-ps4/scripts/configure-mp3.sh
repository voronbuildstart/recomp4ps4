#!/usr/bin/env bash
# Configure mario-party-3-recomp's host (MP3RecompPS4) for the PS4: RT64 on RADV (GNM) through the port's
# VideoOut WSI, RecompFrontend's launcher and menus, SDL2/FreeType from the sysroot. Run through ~/mp3-build
# (no space in the path).
#   configure-mp3.sh [extra cmake args...]
# pthreads are in libkernel, but CMake's probe programs don't link: FindThreads is told.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/ps4-env.sh"
SRC="${CBFD_SRC:-$PS4_BUILD_ROOT/src/mario-party-3-recomp}"
BUILD="$PS4_BUILD_ROOT/build/mp3"
export PS4_SYSROOT="$PS4_BUILD_ROOT/sysroot"
export PKG_CONFIG_LIBDIR="$PS4_SYSROOT/lib/pkgconfig"
unset PKG_CONFIG_PATH

# OpenOrbis' older libc++ is missing two C++20 library details used upstream: the two-iterator
# std::string_view constructor and <compare> for defaulted <=>. Apply both tiny fixes idempotently.
apply_once() {
    local patch_file="$1" marker="$2" target="$3"
    if [ -f "$SRC/$target" ] && ! grep -q "$marker" "$SRC/$target"; then
        patch -p1 -d "$SRC" < "$patch_file"
    fi
}
apply_once "$HERE/../patches/n64recomp-string-view-ps4.patch" "PS4 string_view fix" \
    lib/N64ModernRuntime/N64Recomp/src/mod_symbols.cpp
apply_once "$HERE/../patches/ultramodern-compare-ps4.patch" "needs <compare> for defaulted" \
    lib/N64ModernRuntime/ultramodern/include/ultramodern/config.hpp
apply_once "$HERE/../patches/ultramodern-quick-exit-ps4.patch" "no std::quick_exit" \
    lib/N64ModernRuntime/ultramodern/src/error_handling.cpp

ps4_cmake -S "$SRC" -B "$BUILD" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$HERE/../toolchain/ps4-mp3.cmake" \
    "-DCMAKE_PROJECT_MarioParty3Recompiled_INCLUDE=$HERE/../toolchain/ps4-love-style.cmake" \
    -DMP3_PS4_DIR="$(cd "$HERE/../ps4" && pwd)" \
    -DPS4_PAID="${PS4_PAID:-0x3800000000000035}" \
    -DPS4_MESA_BUILD="$PS4_BUILD_ROOT/build/mesa" \
    -DPS4_SYSROOT="$PS4_SYSROOT" \
    -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    -DPLUTOVG_BUILD_EXAMPLES=OFF \
    -DFREETYPE_LIBRARY="$PS4_SYSROOT/lib/libfreetype.a" \
    -DFREETYPE_INCLUDE_DIR_freetype2="$PS4_SYSROOT/include/freetype2" \
    -DFREETYPE_INCLUDE_DIR_ft2build="$PS4_SYSROOT/include/freetype2" \
    -DSDL2_DIR="$PS4_SYSROOT/lib/cmake/SDL2" \
    -DCMAKE_HAVE_LIBC_PTHREAD=1 -DCMAKE_THREAD_LIBS_INIT= -DThreads_FOUND=TRUE \
    -DBUILD_TESTING=OFF \
    "$@"
