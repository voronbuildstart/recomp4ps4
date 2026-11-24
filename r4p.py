#!/usr/bin/env python3
"""
recomp4ps4 — build N64 static-recompilation ports as installable PS4 packages.

Pipeline it drives:
  1. setup     clone the community recomp project for a game (+ the Conker-PS4
               port template once, shared by all games)
  2. rom       verify your own ROM dump (region, size, SHA-1) and place it
  3. pc        build the PC port  (validates the recomp before touching PS4)
  4. ps4       generate a PS4 port workspace from the Conker-PS4 template and
               build a .pkg with the OpenOrbis toolchain
  5. install   put the .pkg on the PS4 (GoldHEN Package Installer)

What this app CANNOT do: create a recompilation for a game that has no
community recomp project. Each game recipe points at an existing, finished
N64Recomp project (see games/*.json).

What it automates: everything around them — cloning, ROM verification, PC
builds, PS4 workspace generation from the proven Conker-PS4 port layer, and
OpenOrbis packaging. The first PS4 build of a new game is expected to need
hands-on iteration on real hardware; every step logs what it did.
"""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PROJECTS = APP_DIR / "projects"
GAMES_DIR = APP_DIR / "games"
OUT_DIR = APP_DIR / "out"

TEMPLATE_URL = "https://github.com/iHaiDeeZ/Conker-PS4.git"
TEMPLATE_DIR_NAME = "_template-conker-ps4"
TEMPLATE_DIR = PROJECTS / TEMPLATE_DIR_NAME

# Directories of the Conker-PS4 template that are game-agnostic port infra.
# (patches/ is copied too: its sdl2/freetype/tool patches are generic, the
# cbfd-* ones are game-specific and get flagged in PORTING.md.)
TEMPLATE_INFRA_DIRS = ["ps4", "port", "scripts", "toolchain", "patches", "docs"]
# Files worth rewriting when retargeting the template to a new game.
TEXT_SUFFIXES = {
    ".c", ".cpp", ".cc", ".h", ".hpp", ".sh", ".mk", ".cmake", ".json",
    ".md", ".txt", ".yml", ".yaml", ".ini", ".toml", ".py", "",
}

COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


# ----------------------------------------------------------------- helpers --

def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if COLOR else s

def ok(s):    return _c("32", s)
def warn(s):  return _c("33", s)
def err(s):   return _c("31", s)
def bold(s):  return _c("1", s)
def dim(s):   return _c("2", s)

def info(msg):  print(f"  {msg}")
def good(msg):  print(f"  {ok('+')} {msg}")
def w(msg):     print(f"  {warn('!')} {msg}")
def bad(msg):   print(f"  {err('x')} {msg}")


def run(cmd, cwd=None, capture=True, check=True, quiet=False, timeout=None):
    """Run a command; on failure print the tail of its output. Returns the
    CompletedProcess."""
    shown = cmd if isinstance(cmd, str) else " ".join(shlex.quote(str(a)) for a in cmd)
    if not quiet:
        print(dim(f"  $ {shown}"))
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, text=True,
            capture_output=capture, timeout=timeout,
        )
    except FileNotFoundError:
        bad(f"command not found: {shown.split()[0]}")
        sys.exit(1)
    if check and proc.returncode != 0:
        bad(f"command failed (exit {proc.returncode}): {shown}")
        tail = (proc.stdout or "") + (proc.stderr or "")
        tail = tail.strip().splitlines()[-15:]
        for line in tail:
            print(f"    {line}")
        sys.exit(1)
    return proc


def load_recipe(game_id):
    path = GAMES_DIR / f"{game_id}.json"
    if not path.exists():
        bad(f"unknown game '{game_id}'. Known games: {', '.join(list_games())}")
        sys.exit(1)
    return json.loads(path.read_text())


def list_games():
    return sorted(p.stem for p in GAMES_DIR.glob("*.json"))


def game_dir(recipe):
    return PROJECTS / recipe["repo_dir"]


def rom_path(recipe):
    return PROJECTS / "roms" / recipe["rom"]["name"]


def pc_exe(recipe):
    return game_dir(recipe) / recipe["pc"].get("build_dir", "build") / recipe["exe"]


def pkg_path(recipe):
    return OUT_DIR / f"{recipe['ps4']['pkg_name']}.pkg"


def sha1_of(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_z64(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"\x80\x37\x12\x40"
    except OSError:
        return False


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unit == "GiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024.0


def tool(name):
    return shutil.which(name)


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "recomp4ps4/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


# ------------------------------------------------------------------ doctor --

def pkgconfig_exists(lib):
    if not tool("pkg-config"):
        return None
    return run(["pkg-config", "--exists", lib], check=False, quiet=True).returncode == 0


def cmake_version():
    if not tool("cmake"):
        return None
    m = re.search(r"(\d+)\.(\d+)", run(["cmake", "--version"], quiet=True).stdout or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def clang_targets():
    if not tool("clang"):
        return set(), ""
    out = run(["clang", "--print-targets"], quiet=True).stdout or ""
    return {l.split()[0].strip().lower() for l in out.splitlines() if l.strip()}, out


def openorbis_dir():
    cand = os.environ.get("OO_PS4_TOOLCHAIN")
    if cand and Path(cand).exists():
        return Path(cand)
    home = Path.home()
    for c_ in (home / "OpenOrbis/OpenOrbis-PS4-Toolchain",
               home / "OpenOrbis-PS4-Toolchain"):
        if c_.exists():
            return c_
    return None


def package_manager():
    for pm in ("apt-get", "dnf", "pacman", "zypper"):
        if tool(pm):
            return pm
    return None


def os_name():
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return "unknown OS"


def cmd_doctor(args):
    print(bold("recomp4ps4 doctor — environment check"))
    print(dim(f"  host: {os_name()}   projects dir: {PROJECTS}"))

    print(bold("\nPC build tools"))
    rows = []
    for t in ("git", "curl", "cmake", "ninja", "clang", "clang++", "ld.lld", "make", "pkg-config"):
        rows.append((t, tool(t) is not None))
    for name, present in rows:
        (good if present else bad)(f"{name}: {'found' if present else 'MISSING'}")

    ver = cmake_version()
    for gid in list_games():
        need = load_recipe(gid)["pc"].get("cmake_min", "3.20")
        nm, nn = (int(x) for x in need.split("."))
        if ver is None:
            bad(f"cmake {need}+ (needed by {gid}) — not installed")
        elif (ver[0], ver[1]) >= (nm, nn):
            good(f"cmake {ver[0]}.{ver[1]} >= {need} (needed by {gid})")
        else:
            w(f"cmake {ver[0]}.{ver[1]} < {need} required by {gid}")
            info("hint: `python3 -m pip install --user 'cmake>=3.31' ninja` "
                 "or add the Kitware apt repo")

    targets, _ = clang_targets()
    if tool("clang"):
        if "mips" in targets:
            good("clang has the MIPS target (needed by mp3 patches)")
        else:
            w("clang lacks the MIPS target — mp3's patches stage will fail")
            info("hint: install a full-targets clang (apt: clang; pacman: clang)")

    print(bold("\nPC dev libraries (pkg-config)"))
    for lib in ("sdl2", "gtk+-3.0", "freetype2", "vulkan"):
        r = pkgconfig_exists(lib)
        if r is True:
            good(f"{lib}: found")
        elif r is False:
            bad(f"{lib}: NOT found (dev package missing)")
        else:
            w("pkg-config not installed; cannot check libs")

    print(bold("\nPS4 toolchain"))
    oo = openorbis_dir()
    if oo:
        good(f"OpenOrbis toolchain (dev): {oo}")
        cp = oo / "bin/create-pkg"
        (good if cp.exists() else w)(
            f"create-pkg: {'found' if cp.exists() else 'missing in toolchain bin/'}")
    else:
        info("OpenOrbis toolchain (dev): not installed (only needed for "
             "standalone experiments)")
    pacbrew = Path("/opt/pacbrew/ps4/openorbis")
    (good if pacbrew.exists() else bad)(
        f"PacBrew OpenOrbis at {pacbrew}: "
        f"{'found' if pacbrew.exists() else 'NOT found — the template scripts require it'}")
    if not pacbrew.exists():
        info("install the HENkaku-PS4 build root "
             "(github.com/iHaiDeeZ/HENkaku-PS4): PacBrew OpenOrbis, clang+libc++ "
             "sysroot and its RADV Mesa build; set PS4_BUILD_ROOT to it")
    broot = os.environ.get("PS4_BUILD_ROOT")
    if broot:
        (good if Path(broot).exists() else w)(
            f"PS4_BUILD_ROOT={broot}: {'found' if Path(broot).exists() else 'set but missing'}")
    else:
        info("PS4_BUILD_ROOT not set (template default per game: "
             "~/hm64-build, ~/mp3-build, ~/kirby64-build)")

    print(bold("\nConsole"))
    pm = package_manager()
    if pm:
        good(f"package manager: {pm}  (run `{Path(sys.argv[0]).name} install-deps` "
             "for the full install command)")
    else:
        w("no known package manager detected (apt/dnf/pacman/zypper)")
    info("PS4 needs: GoldHEN + its Package Installer + FTP enabled (GoldHEN menu)")
    info("Your ROM dumps are NOT included and are never bundled by this app.")


def cmd_install_deps(args):
    pm = package_manager()
    cmds = {
        "apt-get": ("sudo apt-get update && sudo apt-get install -y "
                    "build-essential cmake ninja-build clang lld pkg-config "
                    "libsdl2-dev libgtk-3-dev libfreetype-dev libvulkan-dev "
                    "mesa-vulkan-drivers"),
        "dnf": ("sudo dnf install -y cmake ninja-build clang lld pkgconf "
                "SDL2-devel gtk3-devel freetype-devel vulkan-headers "
                "mesa-vulkan-drivers"),
        "pacman": ("sudo pacman -S --needed base-devel cmake ninja clang lld "
                   "pkgconf sdl2 gtk3 freetype2 vulkan-headers "
                   "vulkan-validation-layers"),
        "zypper": ("sudo zypper install -y cmake ninja clang lld pkg-config "
                   "SDL2-devel gtk3-devel freetype-devel vulkan-headers "
                   "mesa-vulkan-drivers"),
    }
    if pm not in cmds:
        bad("no supported package manager found; install cmake/ninja/clang/lld "
            "and SDL2/GTK3/freetype/vulkan dev packages manually")
        sys.exit(1)
    print(bold("Suggested install command:\n"))
    print(f"  {cmds[pm]}\n")
    if args.run:
        run(cmds[pm], capture=False)
        good("done")
    else:
        info("dry run — pass --run to execute it")


# ------------------------------------------------------------------- setup --

def clone(url, dest, submodules=True):
    if dest.exists():
        info(f"already cloned: {dest.name}")
        return
    print(bold(f"cloning {url}"))
    run(["git", "clone", "--depth", "1",
         "--recurse-submodules", "--shallow-submodules",
         url, str(dest)], capture=False, check=False, timeout=1800)
    if not dest.exists():
        bad("clone failed")
        sys.exit(1)
    good(f"cloned to {dest}")


def cmd_setup(args):
    if args.game == "template":
        clone(TEMPLATE_URL, TEMPLATE_DIR)
        return
    recipe = load_recipe(args.game)
    clone(recipe["repo"], game_dir(recipe))
    if TEMPLATE_DIR.exists():
        info(f"port template present: {TEMPLATE_DIR.name}")
    else:
        info("port template not cloned yet — run: setup template")


# --------------------------------------------------------------------- rom --

def cmd_rom(args):
    recipe = load_recipe(args.game)
    src = Path(args.rom).expanduser().resolve()
    if not src.exists():
        bad(f"no such file: {src}")
        sys.exit(1)
    if not is_z64(src):
        bad("not a big-endian .z64 ROM (missing N64 magic 0x80371240). "
            "If you have a .v64/.n64 byte-swapped dump, convert it first.")
        sys.exit(1)
    size = src.stat().st_size
    spec = recipe["rom"]
    if spec.get("size_bytes") and size != spec["size_bytes"]:
        bad(f"wrong size: {human(size)} (expected {human(spec['size_bytes'])} "
            f"for the {spec['region']} version)")
        sys.exit(1)
    if spec.get("sha1"):
        got = sha1_of(src)
        if got != spec["sha1"]:
            bad(f"SHA-1 mismatch: {got}\n  expected: {spec['sha1']} "
                f"({spec['region']})")
            info("double-check the dump; wrong-region or hacked ROMs are "
                 "rejected here on purpose")
            sys.exit(1)
        good(f"SHA-1 verified: {got}")
    else:
        w(f"no reference SHA-1 for this game; verified magic + size "
          f"({human(size)}) only")
    dest = rom_path(recipe)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src == dest:
        good(f"ROM already staged at {dest}")
        return
    shutil.copy2(src, dest)
    good(f"ROM staged at {dest}")


# ---------------------------------------------------------------------- pc --

N64RECOMP_URL = "https://github.com/N64Recomp/N64Recomp.git"
N64RECOMP_DIR = PROJECTS / "_N64Recomp"
# HM64's N64ModernRuntime pin (ca568b6) predates N64Recomp 598ce20 ("Live
# recompiler support for PIC jump tables"), which started emitting
# `.got_ram_addr = std::nullopt` into recomp_overlays.inl — a field the tree's
# librecomp/sections.h does not have. Build the tools from the last revision
# before that emission change (verified against the HM64 PC build).
N64RECOMP_REV = "ffb39cd"


def build_n64recomp(gdir, subdir="."):
    """Build the N64Recomp + RSPRecomp tools and copy them into the game repo
    (root by default; some upstreams already have an `N64Recomp/` source
    directory, so their recipe sets a subdirectory instead). Cached: skipped
    when binaries exist."""
    dest = gdir / subdir
    stamp = dest / "N64Recomp"
    if stamp.is_file() and (dest / "RSPRecomp").is_file():
        info(f"N64Recomp tools already present in {subdir}")
        return
    clone(N64RECOMP_URL, N64RECOMP_DIR)
    run(["git", "checkout", "-q", N64RECOMP_REV], cwd=N64RECOMP_DIR, capture=False)
    print(bold("building N64Recomp tools"))
    run(["cmake", "-S", ".", "-B", "build", "-G", "Ninja",
         "-DCMAKE_BUILD_TYPE=Release"], cwd=N64RECOMP_DIR, capture=False)
    run(["cmake", "--build", "build", "--parallel", str(os.cpu_count() or 4)],
        cwd=N64RECOMP_DIR, capture=False)
    dest.mkdir(parents=True, exist_ok=True)
    found = False
    for tool_ in ("N64Recomp", "RSPRecomp"):
        matches = [p for p in (N64RECOMP_DIR / "build").rglob(tool_)
                   if p.is_file() and os.access(p, os.X_OK)]
        if not matches:
            bad(f"{tool_} binary not found after build")
            sys.exit(1)
        shutil.copy2(matches[0], dest / tool_)
        found = True
    if found:
        good(f"N64Recomp + RSPRecomp staged in {subdir}")


def cmd_pc(args):
    recipe = load_recipe(args.game)
    gdir = game_dir(recipe)
    if not gdir.exists():
        bad(f"{recipe['id']} is not cloned yet — run: setup {recipe['id']}")
        sys.exit(1)
    print(bold(f"PC build — {recipe['title']}"))

    if recipe["pc"].get("rom_at_build"):
        rp_in = recipe["pc"]["rom_path_in_repo"]
        target = gdir / rp_in
        if not rom_path(recipe).exists():
            bad(f"this game's build needs its ROM at {rp_in} — run: "
                f"rom {recipe['id']} <path-to-your-dump>")
            sys.exit(1)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copy2(rom_path(recipe), target)
            good(f"ROM copied into repo: {rp_in}")

    ver = cmake_version()
    need = tuple(int(x) for x in recipe["pc"].get("cmake_min", "3.20").split("."))
    if ver and ver < need:
        bad(f"cmake {need[0]}.{need[1]}+ required, found {ver[0]}.{ver[1]}")
        sys.exit(1)

    for step in recipe["pc"]["steps"]:
        step = step.replace("{nproc}", str(os.cpu_count() or 4))
        if step.startswith("@"):
            if step == "@n64recomp":
                print(bold(f"\nstep: {step[1:]}"))
                build_n64recomp(gdir, recipe["pc"].get("n64recomp_subdir", "."))
                continue
            bad(f"unknown built-in step: {step}")
            sys.exit(1)
        print(bold(f"\nstep: {step.split()[0]}"))
        run(shlex.split(step), cwd=gdir, capture=False)

    exe = pc_exe(recipe)
    if exe.exists():
        good(f"built: {exe}")
        info("run it from the repo root so it finds its assets; give it your "
             "ROM when the launcher asks")
    else:
        w(f"expected exe not found at {exe} — check the build log above; "
          f"the project may name it differently (see `readme {recipe['id']}`)")


# --------------------------------------------------------------------- ps4 --

def apply_replacements(root, replacements):
    changed_files, changed_spots = 0, 0
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue
        new = text
        for a, b in replacements.items():
            new = new.replace(a, b)
        if new != text:
            p.write_text(new, encoding="utf-8")
            changed_files += 1
            changed_spots += 1
    return changed_files


def cmd_ps4(args):
    recipe = load_recipe(args.game)
    ps4 = recipe["ps4"]
    workspace = PROJECTS / f"{recipe['id']}-ps4"

    steps = [
        f"1. use template {TEMPLATE_DIR_NAME} (cloned if missing)",
        f"2. copy port infra: ps4/, port/, scripts/, toolchain/, patches/, "
        f"docs/ into {workspace.name}/",
        "3. rename conker-named scripts/files (build-conker.sh -> "
        f"build-{recipe['id']}.sh, toolchain/ps4-conker.cmake, ...)",
        f"4. retarget strings -> title_id {ps4['title_id']}, data dir "
        f"{ps4['data_dir']}, project {ps4.get('project_name')}, build root "
        f"~/{ps4.get('build_root')}",
        "5. write PORTING.md: the real build flow from the template's "
        "DEVELOPMENT.md, adapted to this game",
        "6. optional --build: run build-deps / configure / build scripts, "
        "then package with the template's make-pkg.sh",
    ]
    if args.plan:
        print(bold(f"PS4 plan for {recipe['id']}"))
        for s in steps:
            info(s)
        return

    if not TEMPLATE_DIR.exists():
        info("port template not cloned — cloning it now")
        clone(TEMPLATE_URL, TEMPLATE_DIR)

    if workspace.exists() and not args.force:
        bad(f"workspace already exists: {workspace} (pass --force to rebuild it)")
        sys.exit(1)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)

    print(bold("copying template port infra"))
    copied = []
    for d in TEMPLATE_INFRA_DIRS:
        src = TEMPLATE_DIR / d
        if not src.exists():
            w(f"template dir absent: {d} (skipped)")
            continue
        shutil.copytree(src, workspace / d, dirs_exist_ok=True)
        copied.append(d)
    good(f"copied: {', '.join(copied)}")

    print(bold("renaming conker-named files"))
    renamed = 0
    for p in sorted(workspace.rglob("*")):
        if p.is_file() and "conker" in p.name.lower():
            new_name = p.name
            for a, b in ps4["replacements"].items():
                new_name = new_name.replace(a, b)
            if new_name != p.name:
                p.rename(p.with_name(new_name))
                renamed += 1
    good(f"renamed {renamed} file(s)")

    print(bold("retargeting strings"))
    # patches/ is deliberately excluded: unified diffs must keep byte-exact
    # context lines against the pristine upstream trees they patch, and the
    # game-specific ones need rewriting by hand anyway (see PORTING.md).
    n = 0
    for d in ("ps4", "port", "scripts", "toolchain", "docs"):
        sub = workspace / d
        if sub.exists():
            n += apply_replacements(sub, ps4["replacements"])
    good(f"rewrote {n} file(s) (patches/ left byte-exact on purpose)")

    # The real build flow (from the template's docs/DEVELOPMENT.md), adapted.
    checklist = f"""# Porting checklist — {recipe['title']} on PS4

Generated by recomp4ps4 from the Conker-PS4 template. Mechanical steps are
done (infra copied, files renamed, strings retargeted). The wiring below is
the part that needs eyes on both repos — expect iteration.

## 0. Build root (once, machine-wide)

Install the HENkaku-PS4 build root (github.com/iHaiDeeZ/HENkaku-PS4):
PacBrew OpenOrbis (`/opt/pacbrew/ps4/openorbis`), a clang+libc++ sysroot and
its RADV Mesa build, then:

    export PS4_BUILD_ROOT=~/{ps4.get('build_root')}

## 1. Recompiled game code (from your ROM)

Per the template's flow, the upstream recomp tree lives inside the build root:

    mkdir -p $PS4_BUILD_ROOT/src
    git clone --recurse-submodules {recipe['repo']} \\
        $PS4_BUILD_ROOT/src/{recipe['repo_dir']}

Put your ROM at `{recipe['pc'].get('rom_path_in_repo') or 'the path upstream documents'}`
in that tree and run the upstream recompiler (see upstream docs: `r4p.py read {recipe['id']}:building`).

## 2. PS4 patches

`patches/` in this workspace came from the Conker port and was **not**
retargeted (diffs must keep byte-exact context against pristine upstream
trees). `rt64-ps4.patch` and `recompfrontend-ps4.patch` may apply cleanly to
the pinned revisions in `patches/BASE.txt` — try them first. `cbfd-ps4.patch`
was written against CBFD-Recompiled's `host/` tree and will **not** apply to
{recipe['repo_dir']} (different structure, no `host/` dir): its ideas
(window handling, controller env var, frontend sizes) need translating to
{recipe['repo_dir']}'s own layout by hand.

## 3. Configure, build, package

    scripts/build-deps.sh                 # SDL2 (+PS4 audio) and FreeType into the sysroot
    scripts/configure-{recipe['id']}.sh   # upstream tree with toolchain/ps4-{recipe['id']}.cmake
    scripts/build-{recipe['id']}.sh       # {ps4.get('project_name')} + eboot.bin
    CONKER-like version var, then scripts/make-pkg.sh <stage-dir> \\
        {ps4['title_id']} "{recipe['title']}" 00.01 {ps4.get('content_label')} out/

`r4p.py ps4 {recipe['id']} --build` runs the build scripts for you when the
build root is present; packaging happens automatically if eboot.bin appears.

## 4. Install & debug

    scripts/upload-to-console.sh out/*.pkg      # FTP to the PS4's /data/pkg
    r4p.py install {recipe['id']} --push <ps4-ip>

First boots are the debugging phase: logs land in {ps4['data_dir']}/ on the
console (read them over FTP). `doctor` shows the freeze watchdog/profiler
switches in the quick menu (L3+R3).

Template source: {TEMPLATE_URL}
Upstream recomp: {recipe['repo']}
"""
    (workspace / "PORTING.md").write_text(checklist)
    good(f"checklist written: {workspace / 'PORTING.md'}")

    pacbrew = Path("/opt/pacbrew/ps4/openorbis")
    broot = os.environ.get("PS4_BUILD_ROOT")
    if not pacbrew.exists() or not (broot and Path(broot).exists()):
        w("HENkaku-PS4 build root not fully present (PacBrew OpenOrbis and "
          "PS4_BUILD_ROOT) — workspace is ready, but the PS4 build is not")
        info("see the checklist in PORTING.md; re-run with --build when ready")
        return
    if not args.build:
        info("build root found; pass --build to run the PS4 build")
        return

    print(bold("building PS4 package"))
    sdir = workspace / "scripts"
    env = {**os.environ}
    for step in ("build-deps.sh", f"configure-{recipe['id']}.sh",
                 f"build-{recipe['id']}.sh"):
        script = sdir / step
        if not script.exists():
            bad(f"missing script: {step} — did the rename/retarget go right?")
            sys.exit(1)
        run(["bash", str(script)], cwd=workspace, capture=False, check=False)
    eboot = None
    broot_path = Path(broot)
    for cand in broot_path.rglob("eboot.bin"):
        eboot = cand
        break
    if not eboot:
        w("no eboot.bin found under PS4_BUILD_ROOT yet — the build scripts "
          "ran; fix errors and package manually via make-pkg.sh")
        return
    stage = OUT_DIR / f"stage-{recipe['id']}"
    stage.mkdir(parents=True, exist_ok=True)
    shutil.copy2(eboot, stage / "eboot.bin")
    icon = TEMPLATE_DIR / "assets" / "sce_sys" / "icon0.png"
    (stage / "sce_sys").mkdir(parents=True, exist_ok=True)
    if icon.exists():
        shutil.copy2(icon, stage / "sce_sys" / "icon0.png")
    run(["bash", str(sdir / "make-pkg.sh"), str(stage), ps4["title_id"],
         recipe["title"], "00.01", ps4.get("content_label", "RECOMP"),
         str(OUT_DIR)], cwd=workspace, capture=False, check=False)
    pkgs = sorted(OUT_DIR.glob("*.pkg"))
    if pkgs:
        shutil.copy2(pkgs[-1], pkg_path(recipe))
        good(f"package ready: {pkg_path(recipe)}")
    else:
        w("no .pkg produced yet — check the logs; first ports usually need a "
          "fix inside the workspace (see PORTING.md)")


# ----------------------------------------------------------------- install --

def cmd_install(args):
    recipe = load_recipe(args.game)
    ps4 = recipe["ps4"]
    pkg = pkg_path(recipe)
    if not pkg.exists():
        bad(f"no package built yet: {pkg} (run `ps4 {recipe['id']} --build`)")
        sys.exit(1)
    print(bold(f"Install {recipe['title']} on the PS4 (GoldHEN):"))
    info("GoldHEN watches /data/pkg for packages and offers them in its "
         "Package Installer")
    info(f"1. on the PS4: enable GoldHEN, start its FTP server "
         f"(port {os.environ.get('PS4_FTP_PORT', '2121')})")
    info(f"2. push the pkg:  curl -T {pkg.name} "
         f"ftp://<ps4-ip>:2121/data/pkg/   (or copy to a USB stick, exFAT)")
    info(f"3. GoldHEN -> Package Installer -> install it")
    info(f"4. launch '{recipe['title']}' from the home screen "
         f"(title id {ps4['title_id']}; saves/logs in {ps4['data_dir']})")
    if args.push:
        host = f"ftp://{args.push}:{os.environ.get('PS4_FTP_PORT', '2121')}/data/pkg/"
        run(["curl", "-T", str(pkg), host], capture=False)
        good("uploaded — check the Package Installer on the console")
        info("hint: the template's scripts/upload-to-console.sh in the "
             "workspace does the same with a settle-check (retries if the "
             "upload doesn't stick)")


# ----------------------------------------------------------------- status --

def cmd_status(args):
    print(bold(f"recomp4ps4 status  ({os_name()})"))
    info(f"template: {'ready' if TEMPLATE_DIR.exists() else 'not cloned'}"
         f"  ({TEMPLATE_DIR.name})")
    for gid in list_games():
        recipe = load_recipe(gid)
        gdir, rom, exe = game_dir(recipe), rom_path(recipe), pc_exe(recipe)
        ws = PROJECTS / f"{gid}-ps4"
        parts = [
            ("cloned", gdir.exists()),
            ("rom", rom.exists()),
            ("pc-built", exe.exists()),
            ("ps4-ws", ws.exists()),
            ("pkg", pkg_path(recipe).exists()),
        ]
        flags = "  ".join((ok if v else dim)("•" if v else "○") + f" {k}" for k, v in parts)
        print(f"  {bold(recipe['id']):<8} {flags}")


# ------------------------------------------------------------------ readme --

def cmd_read(args):
    targets = {
        "template": ("https://raw.githubusercontent.com/iHaiDeeZ/Conker-PS4/main/docs/DEVELOPMENT.md",
                     "Conker-PS4 docs/DEVELOPMENT.md (how the PS4 port is built)"),
    }
    for gid in list_games():
        r = load_recipe(gid)
        for name, url in r["docs"].items():
            targets[f"{gid}:{name}"] = (url, f"{r['title']} — {name}")
    key = args.doc
    if key not in targets:
        bad(f"unknown doc '{key}'. Available: {', '.join(sorted(targets))}")
        sys.exit(1)
    url, label = targets[key]
    print(bold(label) + dim(f"  ({url})\n"))
    try:
        print(fetch_text(url))
    except Exception as e:
        bad(f"fetch failed: {e}")


# --------------------------------------------------------------------- gui --

def cmd_gui(args):
    gui = APP_DIR / "gui" / "r4p_gui.py"
    if not gui.exists():
        bad(f"GUI not found: {gui}")
        sys.exit(1)
    idx = next(i for i, a in enumerate(sys.argv) if a == "gui")
    os.execv(sys.executable, [sys.executable, str(gui)] + sys.argv[idx + 1:])


# -------------------------------------------------------------------- main --

def main():
    # `gui` is handled before argparse so its flags pass through untouched.
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        cmd_gui(None)
        return 0
    ap = argparse.ArgumentParser(
        prog="r4p.py",
        description="Build N64 recompilation ports as PS4 packages "
                    "(games: HM64, Mario Party 3, Kirby 64: The Crystal Shards).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check the environment for each stage")
    p = sub.add_parser("install-deps", help="print (or run with --run) the "
                       "package-manager command for PC build deps")
    p.add_argument("--run", action="store_true")
    p = sub.add_parser("setup", help="clone a game's recomp project "
                       "(or the port template: setup template)")
    p.add_argument("game", choices=list_games() + ["template"])
    p = sub.add_parser("rom", help="verify + stage your ROM dump for a game")
    p.add_argument("game", choices=list_games())
    p.add_argument("rom", help="path to your .z64 dump")
    p = sub.add_parser("pc", help="build the PC port of a game (validation "
                       "step before the PS4 build)")
    p.add_argument("game", choices=list_games())
    p = sub.add_parser("ps4", help="generate the PS4 workspace from the "
                       "Conker-PS4 template; --build attempts the pkg")
    p.add_argument("game", choices=list_games())
    p.add_argument("--plan", action="store_true", help="print steps, do nothing")
    p.add_argument("--build", action="store_true")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("install", help="instructions (and optional --push "
                       "IP over FTP) for installing the pkg via GoldHEN")
    p.add_argument("game", choices=list_games())
    p.add_argument("--push", metavar="PS4_IP", help="upload the pkg via FTP")
    sub.add_parser("status", help="what exists so far")
    sub.add_parser("gui", help="graphical launcher for the whole pipeline (args after 'gui' are passed through)")
    p = sub.add_parser("read", help="print an upstream doc (readme/building, "
                       "or 'template')")
    p.add_argument("doc")

    args = ap.parse_args()
    PROJECTS.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)
    table = {"doctor": cmd_doctor, "gui": cmd_gui,
             "install-deps": cmd_install_deps, "setup": cmd_setup, "rom": cmd_rom,
             "pc": cmd_pc, "ps4": cmd_ps4, "install": cmd_install,
             "status": cmd_status, "read": cmd_read}
    table[args.cmd](args)


if __name__ == "__main__":
    main()
