#!/usr/bin/env bash
# Builds the configured PS4 host (configure-gauntlet.sh first): GauntletRecompPS4 and its eboot.bin.
#   build-gauntlet.sh [ninja args...]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/ps4-env.sh"   # PacBrew paths, ld.lld's libxml2 compat
export LD_LIBRARY_PATH=/snap/gaming-graphics-core24/13/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}
BUILD="$PS4_BUILD_ROOT/build/gauntlet"
# ninja's status, not grep's (which fails when there is nothing to show).
# Memory-aware parallelism: ~1.5 GB per compile job, at most nproc jobs
# (the old -j16 default OOM-froze a 2-core / 3.3 GB laptop).
MEM_KB=$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 8388608)
MEM_JOBS=$(( MEM_KB / 1500000 ))
[ "$MEM_JOBS" -lt 1 ] && MEM_JOBS=1
NCPU=$(nproc)
if [ "$MEM_JOBS" -lt "$NCPU" ]; then DEFAULT_JOBS=$MEM_JOBS; else DEFAULT_JOBS=$NCPU; fi
echo "build parallelism: -j${JOBS:-$DEFAULT_JOBS} ($(nproc) cores, $(awk '/MemTotal/{printf "%.1f GB", $2/1048576}' /proc/meminfo) RAM)"
set +o pipefail
# Gauntlet's recompiled functions are pre-generated (no patches.toml rebuild needed).
ninja -C "$BUILD" -j"${JOBS:-$DEFAULT_JOBS}" "$@" 2>&1 | tee "$PS4_BUILD_ROOT/logs/build.log" | grep -E "error:|FAILED|warning: .*undefined|^ninja: build stopped" | head -${ERRORS:-80}
exit "${PIPESTATUS[0]}"
