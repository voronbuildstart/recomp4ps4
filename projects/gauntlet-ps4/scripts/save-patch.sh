#!/usr/bin/env bash
# Exports the PS4 changes in the build tree's checkouts into patches/ (one patch per repository).
# GauntletRecomp's tools carry its own patches (recomp/*.patch), committed in each checkout as
# "GauntletRecomp patches (baseline)" on branch ps4: the PS4 patches are against those commits.
#   save-patch.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${GAUNTLET_SRC:-$HOME/gauntlet-build/src/GauntletRecomp}"
OUT="$HERE/../patches"
mkdir -p "$OUT"
save() {
    local repo="$1" name="$2"
    git -C "$repo" add -A -N . 2>/dev/null || true
    git -C "$repo" diff --binary --ignore-submodules=all HEAD > "$OUT/$name.patch"
    printf '%-28s %s lines\n' "$name.patch" "$(wc -l < "$OUT/$name.patch")"
}
save "$SRC" gauntlet-host-ps4
save "$SRC/lib/N64ModernRuntime" n64modernruntime-ps4
save "$SRC/lib/N64ModernRuntime/N64Recomp/lib/sljit" sljit-ps4
save "$SRC/lib/rt64" rt64-ps4
{
    echo "Base revisions of the PS4 patches (GauntletRecomp's own patches applied first, see save-patch.sh)"
    echo "GauntletRecomp  https://github.com/GauntletRet/GauntletRecomp  $(git -C "$SRC" rev-parse HEAD)"
    for t in lib/N64Recomp lib/N64ModernRuntime lib/N64ModernRuntime/N64Recomp/lib/sljit lib/rt64 lib/gauntlet; do
        echo "$t  $(git -C "$SRC" ls-tree -r HEAD "$t" 2>/dev/null | awk '{print $3}' | head -1 || true)$(git -C "$SRC/$t" rev-parse --short HEAD >/dev/null 2>&1 && echo " (checkout $(git -C "$SRC/$t" rev-parse --short HEAD))")"
    done
    echo "SDL2  https://github.com/libsdl-org/SDL  release-2.32.10"
    echo "FreeType  https://gitlab.freedesktop.org/freetype/freetype  VER-2-13-3"
} > "$OUT/BASE.txt"
