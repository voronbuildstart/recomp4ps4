# Source to build like love-ps4: PacBrew OpenOrbis toolchain (clang 12, ld.lld, create-fself).
PS4_BUILD_ROOT="${PS4_BUILD_ROOT:-$HOME/mp3-build}"
OPENORBIS="${OPENORBIS:-/opt/pacbrew/ps4/openorbis}"
# shellcheck disable=SC1091
source "$OPENORBIS/ps4vars.sh"
# PacBrew's ld.lld links against libxml2.so.2; newer distros only ship libxml2.so.16 (same C
# API). Export the real snap libxml2.so.2 first (matches what the HM64 build does), then a private
# host-compat symlink to libxml2.so.16 as a fallback. Unconditional: a conditional check that
# silently skips the export is how the PS4 link step once died with 127/libxml2 despite the
# compat dir existing.
compat=$(ls /usr/lib/x86_64-linux-gnu/libxml2.so.* 2>/dev/null | grep -E 'libxml2\.so\.[0-9]+$' | head -1)
if [ -n "$compat" ]; then
    mkdir -p "$PS4_BUILD_ROOT/host-compat"
    ln -sf "$compat" "$PS4_BUILD_ROOT/host-compat/libxml2.so.2"
    export LD_LIBRARY_PATH="$PS4_BUILD_ROOT/host-compat${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
fi
for d in /snap/gaming-graphics-core24/*/usr/lib/x86_64-linux-gnu; do
    if [ -f "$d/libxml2.so.2" ]; then
        export LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        break
    fi
done
# ps4vars.sh exports CFLAGS/CXXFLAGS/LDFLAGS for makefile projects; CMake would prepend them to
# the toolchain's own flags (and the CXXFLAGS break <cmath>), so clear them for CMake.
ps4_cmake() {
    env -u CFLAGS -u CXXFLAGS -u CPPFLAGS -u LDFLAGS -u LIBS \
        cmake -DCMAKE_TOOLCHAIN_FILE="$OPENORBIS/cmake/ps4.cmake" -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_POLICY_VERSION_MINIMUM=3.5 "$@"
}
