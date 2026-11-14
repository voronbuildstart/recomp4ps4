#!/usr/bin/env bash
# Build libnfs and libsmb2 (for network shares) for the PS4 from source.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$HOME/ps4-build}"
SYSROOT="${PS4_SYSROOT:-$ROOT/sysroot}"
SRC="$ROOT/src"
BUILD="$ROOT/build"
TOOLCHAIN="$HERE/../projects/hm64-ps4/toolchain/ps4-deps.cmake"
mkdir -p "$SRC" "$BUILD" "$SYSROOT/lib"

if [ ! -d "$SRC/libnfs" ]; then
    echo "cloning libnfs..."
    git clone --depth 1 https://github.com/sahlberg/libnfs.git "$SRC/libnfs"
fi
if [ ! -d "$SRC/libsmb2" ]; then
    echo "cloning libsmb2..."
    git clone --depth 1 https://github.com/sahlberg/libsmb2.git "$SRC/libsmb2"
fi

# OpenOrbis' <netinet/in.h> does not expose sin_len/sin6_len (FreeBSD's sockaddr has them).
sed -i -E 's/^(\s*)sin6?->sin6?_len =.*/\1\/* sin6_len absent on the PS4 *\/;/' "$SRC/libnfs/lib/socket.c"
sed -i -E 's/^(\s*)\(\(struct sockaddr_in6 \*\)&rpc->s\)->sin6_len =.*/\1\/* sin6_len absent on the PS4 *\/;/' "$SRC/libnfs/lib/socket.c"
sed -i -E 's/^(\s*)\(\(struct sockaddr_in \*\)&rpc->s\)->sin_len =.*/\1\/* sin_len absent on the PS4 *\/;/' "$SRC/libnfs/lib/socket.c"

# libsmb2's CMakeLists sets CMAKE_C_FLAGS to "-funwind-tables", dropping our
# toolchain's sysroot flags: append instead
sed -i 's|set(CMAKE_C_FLAGS "-funwind-tables")|set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -funwind-tables")|' "$SRC/libsmb2/CMakeLists.txt"
grep -q "__bswap_32=__builtin_bswap32" "$SRC/libsmb2/CMakeLists.txt" || \
    sed -i 's|      add_definitions(-DPS4_PLATFORM)|      add_definitions(-DPS4_PLATFORM -D__bswap_16=__builtin_bswap16 -D__bswap_32=__builtin_bswap32 -D__bswap_64=__builtin_bswap64)|' \
        "$SRC/libsmb2/CMakeLists.txt"

mkdir -p "$BUILD/libnfs" "$BUILD/libsmb2"
env -u CFLAGS -u CXXFLAGS -u CPPFLAGS -u LDFLAGS -u LIBS \
    cmake -S "$SRC/libnfs" -B "$BUILD/libnfs" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$SYSROOT" -DBUILD_SHARED_LIBS=OFF \
    -DENABLE_TESTS=OFF -DENABLE_EXAMPLES=OFF -DENABLE_UTILS=OFF -DENABLE_DOCUMENTATION=OFF
ninja -C "$BUILD/libnfs" ; ninja -C "$BUILD/libnfs" install

env -u CFLAGS -u CXXFLAGS -u CPPFLAGS -u LDFLAGS -u LIBS \
    cmake -S "$SRC/libsmb2" -B "$BUILD/libsmb2" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$SYSROOT" -DBUILD_SHARED_LIBS=OFF \
    -DENABLE_EXAMPLES=OFF -DENABLE_LIBKRB5=OFF -DENABLE_GSSAPI=OFF
ninja -C "$BUILD/libsmb2" ; ninja -C "$BUILD/libsmb2" install
echo "netfs libs installed to $SYSROOT"
