#!/usr/bin/env bash
# Package the PS4 build (after build-kirby64.sh) as Kirby 64: The Crystal Shards: Recompiled, KIRB00001
# (IV0000-KIRB00001_00-KIRBY64RECOMPPS40.pkg), into out/Kirby64-Recompiled-vXX.YY.pkg. Earlier packages in out/ stay.
#   KIRBY64_VERSION=00.01 package-kirby64.sh
# The package carries the recompiled game code built from your own ROM, and the ROM itself
# (/app0/game/kirby64.z64, which the game reads its data from; stored on first start, so there's no
# Load ROM step): it's for your console only, never to be shared. KIRBY64_ROM picks another ROM file.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/ps4-env.sh"
BUILD="$PS4_BUILD_ROOT/build/kirby64"
SRC="${KIRBY64_SRC:-$PS4_BUILD_ROOT/src/Kirby64Recomp}"
EBOOT="$BUILD/Kirby64Recompiled_eboot/eboot.bin"
ELF="$BUILD/Kirby64Recompiled"
VERSION="${KIRBY64_VERSION:-00.01}"

[ -f "$EBOOT" ] || { echo "missing $EBOOT: build first" >&2; exit 1; }
[ "$EBOOT" -nt "$ELF" ] || { echo "$EBOOT is older than the ELF: the last build failed" >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9]\.[0-9][0-9]$ ]] || { echo "version must look like 01.00" >&2; exit 1; }
STAGE="$PS4_BUILD_ROOT/build/kirby64-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE/sce_sys"
cp "$EBOOT" "$STAGE/eboot.bin"
python3 "$HERE/make-art.py" "$HERE/../assets" "$STAGE/sce_sys" "$SRC/icons/app.png"
echo "$VERSION" > "$STAGE/version.txt"
# RecompFrontend's fonts, icons, style sheet and controller mappings (/app0/assets)
cp -r "$SRC/assets" "$STAGE/assets"
# the quick menu's icons and gradients (ps4/ps4_quick_menu.cpp: "ps4menu/...")
cp -r "$HERE/../assets/menu" "$STAGE/assets/ps4menu"
# the ROM the code was recompiled from (the US ROM; the build checked it). Not in a folder named
# rom: create-gp4 leaves that one out of the package's folder list, and PkgTool then fails.
ROM="${KIRBY64_ROM:-$SRC/NK4E.z64}"
[ -f "$ROM" ] || { echo "missing the ROM ($ROM)" >&2; exit 1; }
mkdir -p "$STAGE/game"
cp "$ROM" "$STAGE/game/kirby64.z64"
# SDL's game-controller mappings for the pad (main.cpp reads them from /app0)
cp "$SRC/recompcontrollerdb.txt" "$STAGE/recompcontrollerdb.txt"
cp "$SRC/LICENSE" "$STAGE/LICENSE.txt"
# PkgTool's pkg_build crashes ("Sequence contains no elements") on empty folders.
find "$STAGE" -type d -empty -delete
# Vulkan (RADV on GNM) runs under the plain homebrew identity (4.5 GiB of direct memory).
PKG="$(SFO_STYLE=plain NO_RIGHT_SPRX=1 DOLPHIN_PS4_MODULES_DIR=/nonexistent "$HERE/make-pkg.sh" "$STAGE" KIRB00001 "Kirby 64: The Crystal Shards: Recompiled" "$VERSION" KIRBY64RECOMPPS4 "$PS4_BUILD_ROOT/out" | tail -1)"
ls -la "$PKG"
# a copy at the repo root, easy to find; *.pkg is ignored by git
REPO_OUT="$(cd "$HERE/../../.." && pwd)/out"
mkdir -p "$REPO_OUT"
NAME="Kirby64-Recompiled-v$VERSION.pkg"
cp "$PKG" "$REPO_OUT/$NAME"
# Keep the symbols of every packaged build: crash logs must be symbolized against the exact binary.
mkdir -p "$PS4_BUILD_ROOT/oelf"
cp "$BUILD/Kirby64Recompiled_eboot/Kirby64Recompiled.oelf" "$PS4_BUILD_ROOT/oelf/v$VERSION.oelf"
cp "$ELF" "$PS4_BUILD_ROOT/oelf/v$VERSION.elf"
echo "out/$NAME is ready; install it on the console from its Package Installer (GoldHEN > Package Installer)."
