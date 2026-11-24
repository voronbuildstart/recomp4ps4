#!/usr/bin/env bash
# Package the PS4 build (after build-gauntlet.sh) as Gauntlet Legends: Recompiled, GAUN00001
# (IV0000-GAUN00001_00-GAUNTLETRECOMP0.pkg), into out/Gauntlet-Recompiled-vXX.YY.pkg. Earlier packages in out/ stay.
#   GAUNTLET_VERSION=00.01 package-gauntlet.sh
# The package carries the recompiled game code built from your own ROM, and the ROM itself
# (/app0/game/gauntlet.z64, which the game reads its data from; stored on first start, so there's no
# Load ROM step): it's for your console only, never to be shared. GAUNTLET_ROM picks another ROM file.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/ps4-env.sh"
BUILD="$PS4_BUILD_ROOT/build/gauntlet"
SRC="${GAUNTLET_SRC:-$PS4_BUILD_ROOT/src/GauntletLegendsRecomp}"
EBOOT="$BUILD/GauntletRecompiled_eboot/eboot.bin"
ELF="$BUILD/GauntletRecompiled"
VERSION="${GAUNTLET_VERSION:-00.01}"

[ -f "$EBOOT" ] || { echo "missing $EBOOT: build first" >&2; exit 1; }
[ "$EBOOT" -nt "$ELF" ] || { echo "$EBOOT is older than the ELF: the last build failed" >&2; exit 1; }
[[ "$VERSION" =~ ^[0-9][0-9]\.[0-9][0-9]$ ]] || { echo "version must look like 01.00" >&2; exit 1; }
STAGE="$PS4_BUILD_ROOT/build/gauntlet-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE/sce_sys"
cp "$EBOOT" "$STAGE/eboot.bin"
ICON="$SRC/icons/app.png"
[ -f "$ICON" ] || ICON="$HERE/../assets/app.png"
python3 "$HERE/make-art.py" "$HERE/../assets" "$STAGE/sce_sys" "$ICON"
echo "$VERSION" > "$STAGE/version.txt"
# the quick menu's icons and gradients (ps4/ps4_quick_menu.cpp: "ps4menu/...")
mkdir -p "$STAGE/assets"
cp -r "$HERE/../assets/menu" "$STAGE/assets/ps4menu"
# the ROM the code was recompiled from (the US ROM; the build checked it). Not in a folder named
# rom: create-gp4 leaves that one out of the package's folder list, and PkgTool then fails.
ROM="${GAUNTLET_ROM:-$HOME/Downloads/Gauntlet Legends/Gauntlet Legends (USA).z64}"
[ -f "$ROM" ] || { echo "missing the ROM ($ROM)" >&2; exit 1; }
mkdir -p "$STAGE/game"
cp "$ROM" "$STAGE/game/gauntlet.z64"
cp "$SRC/LICENSE" "$STAGE/LICENSE.txt"
# PkgTool's pkg_build crashes ("Sequence contains no elements") on empty folders.
find "$STAGE" -type d -empty -delete
# Vulkan (RADV on GNM) runs under the plain homebrew identity (4.5 GiB of direct memory).
PKG="$(SFO_STYLE=plain NO_RIGHT_SPRX=1 DOLPHIN_PS4_MODULES_DIR=/nonexistent "$HERE/make-pkg.sh" "$STAGE" GAUN00001 "Gauntlet Legends: Recompiled" "$VERSION" GAUNTLETRECOMP "$PS4_BUILD_ROOT/out" | tail -1)"
ls -la "$PKG"
# a copy at the repo root, easy to find; *.pkg is ignored by git
REPO_OUT="$(cd "$HERE/../../.." && pwd)/out"
mkdir -p "$REPO_OUT"
NAME="Gauntlet-Recompiled-v$VERSION.pkg"
cp "$PKG" "$REPO_OUT/$NAME"
# Keep the symbols of every packaged build: crash logs must be symbolized against the exact binary.
mkdir -p "$PS4_BUILD_ROOT/oelf"
cp "$BUILD/GauntletRecompiled_eboot/GauntletRecompiled.oelf" "$PS4_BUILD_ROOT/oelf/v$VERSION.oelf"
cp "$ELF" "$PS4_BUILD_ROOT/oelf/v$VERSION.elf"
echo "out/$NAME is ready; install it on the console from its Package Installer (GoldHEN > Package Installer)."
