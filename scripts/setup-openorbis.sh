#!/usr/bin/env bash
# Download and extract the PacBrew OpenOrbis PS4 toolchain into
# /opt/pacbrew/ps4/openorbis (override with OPENORBIS=<prefix>).
# Requires root (pkexec) for the default prefix; override with OPENORBIS=~/.ps4-openorbis
# for a home install (state the path in env.sh).
set -euo pipefail

OPENORBIS="${OPENORBIS:-/opt/pacbrew/ps4/openorbis}"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

if [ -x "$OPENORBIS/bin/create-fself" ]; then
    echo "OpenOrbis already installed at $OPENORBIS — skipping download."
    echo "set OPENORBIS=<prefix> and delete this directory to force a fresh install."
    exit 0
fi

packages=(
    ps4-openorbis-musl-1.5-2-any
    ps4-openorbis-headers-0.5.2-4-any
    ps4-openorbis-create-fself-1.2-3-any
    ps4-openorbis-create-gp4-1.0-5-any
    ps4-openorbis-pkgtools-0.2.231-5-any
    ps4-openorbis-vars-1.1-3-any
    ps4-openorbis-zlib-1.3.1-2-any
)
base="https://pacman.mydedibox.fr/pacbrew/packages"

echo "downloading Pacbrew OpenOrbis packages (~70 MB)..."
for pkg in "${packages[@]}"; do
    url="$base/$pkg.pkg.tar.xz"
    out="$TMPDIR/$pkg.pkg.tar.xz"
    [ -s "$out" ] && continue
    echo "  $pkg"
    curl -sS --connect-timeout 20 -L -o "$out" "$url"
done

echo "installing into $OPENORBIS (needs root for the default prefix)..."
if [ "$OPENORBIS" = "/opt/pacbrew/ps4/openorbis" ]; then
    if [ "$(id -u)" -ne 0 ]; then
        for f in "$TMPDIR"/ps4-*.pkg.tar.xz; do
            pkexec tar -xJf "$f" -C /
        done
    else
        for f in "$TMPDIR"/ps4-*.pkg.tar.xz; do
            tar -xJf "$f" -C /
        done
    fi
else
    mkdir -p "$(dirname "$OPENORBIS")"
    ( cd "$OPENORBIS" && \
      tar -xJf "$TMPDIR"/ps4-openorbis-musl-1.5-2-any.pkg.tar.xz --strip-components=4 )
    ( cd "$OPENORBIS" && \
      tar -xJf "$TMPDIR"/ps4-openorbis-headers-0.5.2-4-any.pkg.tar.xz --strip-components=4 )
    ( cd "$OPENORBIS" && \
      tar -xJf "$TMPDIR"/ps4-openorbis-create-fself-1.2-3-any.pkg.tar.xz --strip-components=4 )
    ( cd "$OPENORBIS" && \
      tar -xJf "$TMPDIR"/ps4-openorbis-create-gp4-1.0-5-any.pkg.tar.xz --strip-components=4 )
    ( cd "$OPENORBIS" && \
      tar -xJf "$TMPDIR"/ps4-openorbis-pkgtools-0.2.231-5-any.pkg.tar.xz --strip-components=4 )
    ( cd "$OPENORBIS" && \
      tar -xJf "$TMPDIR"/ps4-openorbis-vars-1.1-3-any.pkg.tar.xz --strip-components=4 )
    ( cd "$OPENORBIS" && \
      tar -xJf "$TMPDIR"/ps4-openorbis-zlib-1.3.1-2-any.pkg.tar.xz --strip-components=4 )
fi

echo "OpenOrbis ready at $OPENORBIS"
find "$OPENORBIS" -maxdepth 3 -type d | sort
