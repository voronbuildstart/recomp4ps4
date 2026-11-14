#!/usr/bin/env bash
# Cross-builds Mesa's RADV (Vulkan for AMD GCN) for the PS4 (same recipe as DolphinPS4).
# Mesa source: $ROOT/src/mesa (mesa-26.0.8 with the PS4 patch, see setup-mesa.sh).
# Host tools: meson/mako/pyyaml in mesa-venv.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="${1:-$HOME/ps4-build}"
SYSROOT="${PS4_SYSROOT:-$ROOT/sysroot}"
MESA="$ROOT/src/mesa"
BUILD="$ROOT/build/mesa"
OPENORBIS="${OPENORBIS:-/opt/pacbrew/ps4/openorbis}"

export PATH="$ROOT/mesa-venv/bin:$PATH"
if [ ! -d "$ROOT/mesa-venv/bin" ]; then
    echo "creating mesa-venv (python + meson + mako + pyyaml)..."
    python3 -m venv "$ROOT/mesa-venv"
    "$ROOT/mesa-venv/bin/pip" install --quiet meson mako pyyaml packaging
fi

# Header-only libdrm / libdrm_amdgpu packages for meson's dependency() checks.
pkgconfig="$ROOT/mesa-pkgconfig"
mkdir -p "$pkgconfig"
cat > "$pkgconfig/libdrm_amdgpu.pc" <<EOF
Name: libdrm_amdgpu
Description: libdrm headers only (PS4 has no DRM)
Version: 2.4.125
Cflags: -I$ROOT/src/libdrm -I$ROOT/src/libdrm/include/drm -I$ROOT/src/libdrm/amdgpu
Libs:
EOF

# mesa build cross file
cross="$ROOT/mesa-ps4-cross.ini"
cat > "$cross" <<EOF
[binaries]
c = 'clang-21'
cpp = 'clang++-21'
ar = 'llvm-ar-21'
strip = 'llvm-strip-21'
pkg-config = 'pkg-config'

[properties]
needs_exe_wrapper = true
pkg_config_libdir = '$pkgconfig'

[built-in options]
c_args = ['-target', 'x86_64-pc-freebsd12-elf', '-D_GNU_SOURCE', '-D__PS4__', '-D__ORBIS__', '-D__OPENORBIS__', '-DPS4', '-D__BSD_VISIBLE', '-D_BSD_SOURCE', '-fPIC', '-funwind-tables', '-march=btver2', '-isysroot', '$OPENORBIS', '-isystem', '$SYSROOT/libc-overlay', '-isystem', '$HERE/../projects/hm64-ps4/port/mesa-overlay', '-I$ROOT/src/libdrm', '-I$ROOT/src/libdrm/include/drm', '-isystem', '$OPENORBIS/include', '-I$OPENORBIS/usr/include']
cpp_args = ['-nostdinc++', '-isystem', '$SYSROOT/include/c++/v1', '-target', 'x86_64-pc-freebsd12-elf', '-D_GNU_SOURCE', '-D__PS4__', '-D__ORBIS__', '-D__OPENORBIS__', '-DPS4', '-D__BSD_VISIBLE', '-D_BSD_SOURCE', '-fPIC', '-funwind-tables', '-march=btver2', '-isysroot', '$OPENORBIS', '-isystem', '$SYSROOT/libc-overlay', '-isystem', '$HERE/../projects/hm64-ps4/port/mesa-overlay', '-I$ROOT/src/libdrm', '-I$ROOT/src/libdrm/include/drm', '-isystem', '$OPENORBIS/include', '-I$OPENORBIS/usr/include']
c_link_args = ['-fuse-ld=/usr/bin/ld.lld-21', '-nostdlib', '-Wl,-m,elf_x86_64', '-Wl,-pie', '-Wl,--eh-frame-hdr', '-Wl,--script,$OPENORBIS/link.x', '-L$OPENORBIS/lib', '$OPENORBIS/lib/crt1.o', '-lkernel', '-lc', '-lclang_rt.builtins-x86_64', '-lSceLibcInternal']
cpp_link_args = ['-fuse-ld=/usr/bin/ld.lld-21', '-nostdlib', '-Wl,-m,elf_x86_64', '-Wl,-pie', '-Wl,--eh-frame-hdr', '-Wl,--script,$OPENORBIS/link.x', '-L$OPENORBIS/lib', '$OPENORBIS/lib/crt1.o', '-lkernel', '-lc', '-lclang_rt.builtins-x86_64', '-lSceLibcInternal', '$SYSROOT/lib/libc++.a', '$SYSROOT/lib/libc++abi.a', '$OPENORBIS/lib/libunwind.a']

[host_machine]
system = 'freebsd'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF

# Mesa's ac_ps4_drm.c needs to be present for the PS4 DRM implementation
# (it comes in the port's mesa-overlay as port/mesa/ac_ps4_drm.c)
cp "$HERE/../projects/hm64-ps4/port/mesa/ac_ps4_drm.c" "$MESA/src/amd/common/ac_ps4_drm.c"

if [ ! -f "$BUILD/build.ninja" ]; then
    echo "configuring Mesa cross build..."
    PKG_CONFIG_LIBDIR="$pkgconfig" meson setup "$BUILD" "$MESA" --cross-file "$cross" \
        -Dbuildtype=release -Db_ndebug=true -Ddefault_library=static \
        -Dvulkan-drivers=amd -Dgallium-drivers= -Dplatforms= -Dllvm=disabled \
        -Damd-use-llvm=false -Dopengl=false -Dgles1=disabled -Dgles2=disabled -Dglx=disabled \
        -Degl=disabled -Dgbm=disabled -Dzstd=disabled -Dexpat=disabled -Dxmlconfig=disabled \
        -Dvalgrind=disabled -Dlibunwind=disabled -Dlmsensors=disabled -Dbuild-tests=false \
        -Dshader-cache=disabled -Dvulkan-layers= -Dtools= -Dvideo-codecs= -Dspirv-tools=disabled \
        -Dperfetto=false -Dselinux=false -Dallow-fallback-for=libdrm
fi

echo "building Mesa RADV..."
ninja -C "$BUILD" \
    src/amd/vulkan/libvulkan_radeon.a src/amd/addrlib/libaddrlib.a \
    src/amd/common/libamd_common.a src/amd/compiler/libaco.a src/c11/impl/libmesa_util_c11.a \
    src/compiler/libcompiler.a src/compiler/nir/libnir.a src/compiler/spirv/libvtn.a \
    src/util/blake3/libblake3.a src/util/libmesa_util.a src/util/libmesa_util_clflush.a \
    src/util/libmesa_util_clflushopt.a src/util/libmesa_util_simd.a src/util/libparson.a \
    src/util/libxmlconfig.a src/vulkan/runtime/libvulkan_instance.a \
    src/vulkan/runtime/libvulkan_runtime.a src/vulkan/util/libvulkan_util.a \
    src/vulkan/wsi/libvulkan_wsi.a
echo "Mesa RADV built: $BUILD/src/amd/vulkan/libvulkan_radeon.a"
