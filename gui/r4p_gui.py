#!/usr/bin/env python3
"""
recomp4ps4 GUI — turn your own N64 ROM dump into an installable PS4 package.

A GTK3 front-end for the whole pipeline (doctor, clone, ROM verify, recompile,
PS4 build, package, console upload). It does not download ROMs and it never
ships or embeds any game assets: you supply your own dump.

    python3 r4p.py gui            # or: python3 gui/r4p_gui.py
    python3 r4p.py gui --self-test  # checks logic + environment, then exits
"""
import argparse
import configparser
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR))

import r4p  # the CLI app: recipes, helpers (no side effects on import)

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

SETTINGS_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "recomp4ps4"
SETTINGS_FILE = SETTINGS_DIR / "settings.ini"

# The steps the GUI drives, in order. Each returns (ok, detail).
def _default_root(game):
    # Fresh installs share one unified build root; if this machine still has a
    # per-game tree from before that (e.g. ~/hm64-build from earlier work),
    # reuse it instead of starting an expensive rebuild from zero.
    unified = Path.home() / "ps4-build"
    if unified.exists() or not game:
        return str(unified)
    legacy = Path.home() / f"{game}-build"
    return str(legacy) if legacy.exists() else str(unified)

def _resolve(path_str):
    try:
        return Path(path_str).expanduser().resolve()
    except OSError:
        return Path(path_str).expanduser()


def _mesa_lib(root):
    return _resolve(str(Path(root) / "build" / "mesa" / "src" / "amd" / "vulkan" / "libvulkan_radeon.a"))


class Step:
    """One row: name, function(progress, cancel) -> (bool, detail)."""
    def __init__(self, key, title, summary):
        self.key = key
        self.title = title
        self.summary = summary
        self.state = "pending"  # pending | running | ok | failed
        self.detail = ""

    def reset(self):
        self.state = "pending"
        self.detail = ""


class BuildPipeline:
    """Build steps for one game. Runs in a worker thread; UI polls state."""

    def __init__(self, game, build_root, log, cancel_event):
        self.game = game
        self.recipe = r4p.load_recipe(game)
        self.root = Path(build_root).expanduser()
        self.log = log
        self.cancel = cancel_event
        self.steps = [
            Step("toolchain", "Check PS4 toolchain", "PacBrew OpenOrbis + Mesa RADV must be present"),
            Step("clone", "Clone the recomp project", "the community recompiler for this game"),
            Step("rom", "Verify & stage your ROM", "SHA-1 checked; copied into the build tree"),
            Step("recompile", "Recompile the game", "your ROM becomes recompiled C code"),
            Step("sysroot", "PS4 libraries (SDL2, FreeType)", "built into the PS4 sysroot"),
            Step("mesa", "RADV (Vulkan) Mesa check", "the GPU driver the game renders with"),
            Step("configure", "Configure the PS4 build", "cmake with the PS4 toolchain"),
            Step("build", "Build for PS4", "compiles everything; can take a while"),
            Step("package", "Package the .pkg", "installable on your PS4 (GoldHEN)"),
        ]

    # ------------------------------------------------------- utilities --
    def run(self, cmd, cwd=None, env=None, check=True, quiet=True):
        shown = cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)
        self.log(f"  $ {shown}")
        proc = subprocess.Popen(
            cmd, cwd=str(cwd) if cwd else None,
            env={**os.environ, **(env or {})},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace", start_new_session=True,
        )
        tail = []
        for line in proc.stdout:
            if self.cancel.is_set():
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
            line = line.rstrip("\n")
            tail.append(line)
            self.log("    " + line)
            if len(tail) > 400:
                tail.pop(0)
        proc.wait()
        if check and proc.returncode != 0:
            self.log(f"  command failed ({proc.returncode}); last lines:")
            for line in tail[-25:]:
                self.log("    " + line)
            return False
        return True

    def bash(self, script, cwd=None, env=None, check=True):
        return self.run(["bash", "-lc", script], cwd=cwd, env=env, check=check, quiet=False)

    # ------------------------------------------------------------- steps --
    def check_toolchain(self):
        pacbrew = Path("/opt/pacbrew/ps4/openorbis")
        if not pacbrew.exists():
            self.log("  PacBrew OpenOrbis not found at /opt/pacbrew/ps4/openorbis.")
            self.log("  Run the Environment tab's Fresh-machine setup, or build HENkaku-PS4 manually (github.com/iHaiDeeZ/HENkaku-PS4),")
            self.log("  then re-run this step.")
            return False, "PS4 toolchain missing"
        self.log(f"  PacBrew OpenOrbis: {pacbrew}")
        return True, str(pacbrew)

    def clone_upstream(self):
        game_dir = self.root / "src" / self.recipe["repo_dir"]
        if game_dir.exists():
            self.log(f"  already cloned: {game_dir}")
            return True, "already cloned"
        ok = self.run(["git", "clone", "--depth", "1", "--recurse-submodules", "--shallow-submodules",
                       self.recipe["repo"], str(game_dir)], check=True)
        return ok, ("cloned" if ok else "clone failed")

    def stage_rom(self, rom_src):
        game_dir = self.root / "src" / self.recipe["repo_dir"]
        rom_rel = self.recipe["pc"].get("rom_path_in_repo") or f"roms/{self.recipe['rom']['name']}"
        target = game_dir / rom_rel
        want_sha = self.recipe["rom"]["sha1"]
        if not rom_src:
            self.log("  no ROM selected yet — pick your dump on the ROM tab.")
            return False, "no ROM"
        rom_src = Path(rom_src).expanduser()
        if not rom_src.exists():
            return False, f"not found: {rom_src}"
        self.log(f"  verifying {rom_src.name} (SHA-1)...")
        digest = r4p.sha1_of(rom_src)
        if digest != want_sha:
            self.log(f"  SHA-1 MISMATCH\n  got      {digest}\n  expected {want_sha}")
            return False, "wrong ROM (SHA-1 mismatch)"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rom_src, target)
        self.log(f"  ROM OK — copied to {target}")
        return True, "verified & staged"

    def recompile_game(self):
        game_dir = self.root / "src" / self.recipe["repo_dir"]
        if not game_dir.exists():
            return False, "clone first"
        # mp3 ships tools/recompile.sh; hm64 uses the N64Recomp tools from its N64ModernRuntime
        if (game_dir / "tools" / "recompile.sh").exists():
            ok = self.run(["bash", "tools/recompile.sh",
                           "-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++"],
                          cwd=game_dir, env={"PATH": os.environ["PATH"]})
            return ok, ("recompiled" if ok else "recompile failed")
        # hm64 upstream flow: prebuilt recompilers at the repo root, built once
        # from the pinned standalone N64Recomp checkout. The in-tree submodule
        # carries the PS4 boot-trace instrumentation, which does not link for
        # host tools, so never build the tools from there.
        n64bin = game_dir / "N64Recomp"
        rspbin = game_dir / "RSPRecomp"
        if not (n64bin.exists() and rspbin.exists()):
            src = APP_DIR / "projects" / "_N64Recomp"
            if not (src / ".git").exists():
                self.log(f"  cloning N64Recomp into {src} ...")
                if not self.run(["git", "clone", r4p.N64RECOMP_URL, str(src)]):
                    return False, "N64Recomp clone failed"
                if not self.run(["git", "-C", str(src), "checkout", "-q", r4p.N64RECOMP_REV]):
                    return False, "N64Recomp checkout failed"
            self.log("  building N64Recomp tools (one time only)...")
            ok = self.run(["cmake", "-S", str(src), "-B", str(src / "build"),
                           "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release"])
            if not ok:
                return False, "recompiler configure failed"
            ok = self.run(["ninja", "-C", str(src / "build"), "N64Recomp", "RSPRecomp"])
            if not ok:
                return False, "recompiler build failed"
            for tool in ("N64Recomp", "RSPRecomp"):
                matches = sorted(p for p in (src / "build").rglob(tool)
                                 if p.is_file() and os.access(p, os.X_OK))
                if not matches:
                    return False, f"{tool} binary not found after build"
                shutil.copy2(matches[0], game_dir / tool)
            self.log("  recompilers staged in repo root")
        else:
            self.log("  recompilers already present in repo root")
        rom = game_dir / "hm64.us.z64"
        toml = game_dir / "hm64.us.toml"
        rsp_toml = game_dir / "n_aspMain.toml"
        if not (rom.exists() and toml.exists() and rsp_toml.exists()):
            return False, "ROM or .toml missing"
        ok1 = self.run([str(n64bin), str(toml)], cwd=game_dir)
        ok2 = self.run([str(rspbin), str(rsp_toml)], cwd=game_dir)
        return (ok1 and ok2), ("recompiled" if (ok1 and ok2) else "recompile failed")

    def sysroot_deps(self):
        env = {"PS4_BUILD_ROOT": str(self.root)}
        for name, url, ref in (("SDL2", "https://github.com/libsdl-org/SDL", "release-2.32.10"),
                               ("freetype", "https://gitlab.freedesktop.org/freetype/freetype", "VER-2-13-3")):
            dest = self.root / "src" / name
            if not dest.exists():
                self.log(f"  cloning {name} ({ref})...")
                ok = self.run(["git", "clone", "--depth", "1", "--branch", ref, url, str(dest)])
                if not ok:
                    return False, f"{name} clone failed"
            else:
                self.log(f"  {name} already cloned: {dest}")
        # apply the port's SDL2 driver patch (idempotent)
        ps4_sdl_patch = APP_DIR / "projects"
        patch = None
        for cand in ps4_sdl_patch.glob("*/patches/sdl2-ps4.patch"):
            patch = cand
            break
        if patch:
            self.run(["git", "-C", str(self.root / "src" / "SDL2"), "apply", str(patch)], check=False)
        build_deps = APP_DIR / f"projects/{self.game}-ps4/scripts/build-deps.sh"
        if not build_deps.exists():
            return False, f"missing {build_deps}"
        ok = self.bash(f"bash {build_deps}", env=env)
        return ok, ("sysroot ready" if ok else "sysroot build failed")

    def mesa_check(self):
        lib = _mesa_lib(self.root)
        if lib.exists():
            self.log(f"  RADV Mesa library: {lib}")
            return True, str(lib)
        other = None
        for cand in (self.root.parent / ("hm64-build" if self.game == "mp3" else "mp3-build"),
                     Path.home() / ("hm64-build" if self.game == "mp3" else "mp3-build")):
            if _mesa_lib(cand).exists():
                other = _resolve(str(cand / "build" / "mesa"))
                break
        if other is not None:
            link = _resolve(str(self.root / "build" / "mesa"))
            if link.exists():
                return True, "mesa link exists"
            link.parent.mkdir(parents=True, exist_ok=True)
            try:
                link.symlink_to(other)
                self.log(f"  linked shared Mesa from {other}")
                return True, "linked shared Mesa"
            except OSError as e:
                self.log(f"  could not symlink Mesa: {e}")
        self.log("  Mesa RADV is not built in this build root yet.")
        self.log("  Run the Environment tab's Fresh-machine setup to build it, then re-run the build.")
        return False, "Mesa missing"

    def configure_build(self):
        script = APP_DIR / f"projects/{self.game}-ps4/scripts/configure-{self.game}.sh"
        if not script.exists():
            return False, f"missing {script}"
        ok = self.bash(f"bash {script}", env={"PS4_BUILD_ROOT": str(self.root)})
        return ok, ("configured" if ok else "configure failed")

    def build_game(self):
        script = APP_DIR / f"projects/{self.game}-ps4/scripts/build-{self.game}.sh"
        if not script.exists():
            return False, f"missing {script}"
        ok = self.bash(f"bash {script}", env={"PS4_BUILD_ROOT": str(self.root)})
        return ok, ("built" if ok else "build failed")

    def package_game(self):
        script = APP_DIR / f"projects/{self.game}-ps4/scripts/package-{self.game}.sh"
        if not script.exists():
            return False, f"missing {script}"
        version_var = "HM64_VERSION" if self.game == "hm64" else "MP3_VERSION"
        ok = self.bash(f"bash {script}", env={"PS4_BUILD_ROOT": str(self.root), version_var: "00.01"})
        pkg = sorted((APP_DIR / "out").glob("*.pkg"))
        if ok and pkg:
            return True, pkg[-1].name
        return ok, ("packaged" if ok else "package failed")

    def run_step(self, step, rom_src):
        return {
            "toolchain": lambda: self.check_toolchain(),
            "clone": lambda: self.clone_upstream(),
            "rom": lambda: self.stage_rom(rom_src),
            "recompile": lambda: self.recompile_game(),
            "sysroot": lambda: self.sysroot_deps(),
            "mesa": lambda: self.mesa_check(),
            "configure": lambda: self.configure_build(),
            "build": lambda: self.build_game(),
            "package": lambda: self.package_game(),
        }[step.key]()


# --------------------------------------------------------------------------

class AppWindow:
    def __init__(self, self_test=False):
        self.self_test = self_test
        self.settings = self.load_settings()
        self.pipelines = {}
        self.rom_candidates = self.detect_roms()

        self.win = Gtk.Window(title="recomp4ps4 — build your own PS4 package")
        self.win.set_default_size(1080, 760)
        self.win.connect("destroy", Gtk.main_quit)

        hb = Gtk.HeaderBar()
        hb.set_show_close_button(True)
        hb.set_title("recomp4ps4")
        hb.set_subtitle("your ROM dump in, your .pkg out — nothing else")
        self.win.set_titlebar(hb)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.win.add(outer)

        # legal strip
        legal = Gtk.Label(ellipsize=Pango.EllipsizeMode.END)
        legal.set_markup(
            '<span size="small" foreground="#b45309">⚠ You provide your own legally obtained ROM dump. '
            'No ROMs are included, downloaded or redistributed. Packages are for <b>your</b> PS4, personal use.</span>')
        legal.set_margin_top(4)
        legal.set_margin_bottom(4)
        legal.set_xalign(0)
        outer.pack_start(legal, False, False, 0)

        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(230)
        outer.pack_start(paned, True, True, 0)

        # ---------------- sidebar ----------------
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        side.set_border_width(8)
        side.pack_start(Gtk.Label(label="", xalign=0), False, False, 2)
        head = Gtk.Label()
        head.set_markup("<b>Games</b>")
        head.set_xalign(0)
        side.pack_start(head, False, False, 4)

        self.game_list = Gtk.ListBox()
        self.game_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        side.pack_start(self.game_list, True, True, 0)

        for gid in r4p.list_games():
            recipe = r4p.load_recipe(gid)
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_border_width(6)
            title = Gtk.Label()
            title.set_markup(f"<b>{GLib.markup_escape_text(recipe['title'])}</b>")
            title.set_xalign(0)
            box.pack_start(title, False, False, 0)
            sub = Gtk.Label()
            sub.set_markup(f'<span size="smaller" foreground="#666666">{GLib.markup_escape_text(recipe["notes"][0])}</span>')
            sub.set_xalign(0)
            sub.set_line_wrap(True)
            box.pack_start(sub, False, False, 0)
            row.add(box)
            row.game_id = gid
            self.game_list.add(row)

        tools_head = Gtk.Label()
        tools_head.set_markup("<b>Tools</b>")
        tools_head.set_xalign(0)
        side.pack_start(tools_head, False, False, 4)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        for label, page_id in (("🛠  Environment", "env"), ("🎮  Console", "console"), ("⚙  Settings", "settings"), ("ⓘ  About", "about")):
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self.show_page, page_id)
            side.pack_start(btn, False, False, 0)

        paned.pack1(side, False, False)

        # ---------------- main area ----------------
        self.main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        paned.pack2(self.main, True, True)

        self.stack.set_vhomogeneous(False)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)
        self.main.pack_start(self.stack, True, True, 0)

        for gid in r4p.list_games():
            self.stack.add_named(self.build_game_page(gid), f"game-{gid}")
        self.stack.add_named(self.build_env_page(), "env")
        self.stack.add_named(self.build_console_page(), "console")
        self.stack.add_named(self.build_settings_page(), "settings")
        self.stack.add_named(self.build_about_page(), "about")

        # log pane
        log_frame = Gtk.Frame(label="Build log")
        log_frame.set_margin_top(4)
        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_monospace(True)
        self.log_view.set_size_request(-1, 150)
        self.log_buffer = self.log_view.get_buffer()
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.ALWAYS)
        scroller.add(self.log_view)
        log_frame.add(scroller)
        self.main.pack_start(log_frame, False, True, 0)

        self.game_list.connect("row-selected", self.on_row_selected)
        first = self.game_list.get_row_at_index(0)
        if first is not None:
            self.game_list.select_row(first)

    # ------------------------------------------------------- helpers --
    def load_settings(self):
        cp = configparser.ConfigParser()
        cp.read([SETTINGS_FILE])
        return cp

    def save_settings(self):
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            self.settings.write(f)

    def opt(self, section, key, default=""):
        return self.settings.get(section, key, fallback=default)

    def set_opt(self, section, key, value):
        if not self.settings.has_section(section):
            self.settings.add_section(section)
        self.settings.set(section, key, value)
        self.save_settings()

    def detect_roms(self):
        roms = {}
        for gid in r4p.list_games():
            p = APP_DIR / "projects" / "roms" / r4p.load_recipe(gid)["rom"]["name"]
            if p.exists():
                roms[gid] = str(p)
        return roms

    def build_root_for(self, gid):
        return self.opt(f"paths:{gid}", "build_root", _default_root(gid))

    def logf(self, text):
        GLib.idle_add(self._append_log, text)

    def _append_log(self, text):
        self.log_buffer.insert(self.log_buffer.get_end_iter(), text + "\n")
        self.log_view.scroll_to_iter(self.log_buffer.get_end_iter(), 0.0, False, 0, 0)
        return False

    def show_page(self, _btn, pid):
        # Switch to a Tools page and clear the game-list selection, otherwise
        # clicking the already-selected game row fires no row-selected signal
        # and the user is stuck on the Tools page.
        self.stack.set_visible_child_name(pid)
        self.game_list.unselect_all()

    def show_game(self, gid):
        self.stack.set_visible_child_name(f"game-{gid}")

    # -------------------------------------------------- game page --
    def build_game_page(self, gid):
        recipe = r4p.load_recipe(gid)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_border_width(10)

        title = Gtk.Label()
        title.set_markup(f"<span size='x-large' weight='bold'>{GLib.markup_escape_text(recipe['title'])}</span>")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)

        notes = Gtk.Label()
        notes.set_markup('<span foreground="#666666">' + GLib.markup_escape_text(recipe["notes"][0]) + '</span>')
        notes.set_xalign(0)
        notes.set_line_wrap(True)
        page.pack_start(notes, False, False, 0)

        # step list
        self.step_boxes = getattr(self, "step_boxes", {})
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title2 = Gtk.Label()
        title2.set_markup("<b>Build steps</b>")
        title2.set_xalign(0)
        page.pack_start(title2, False, False, 0)
        step_model = BuildPipeline(gid, self.build_root_for(gid), self.logf, threading.Event())
        self.pipelines[gid] = step_model
        for step in step_model.steps:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.set_border_width(2)
            dot = Gtk.Label(label="○")
            dot.set_width_chars(2)
            step_lbl = Gtk.Label()
            step_lbl.set_xalign(0)
            step_lbl.set_markup(f"<b>{GLib.markup_escape_text(step.title)}</b>\n<span size='smaller' foreground='#666666'>{GLib.markup_escape_text(step.summary)}</span>")
            step_lbl.set_line_wrap(True)
            row.pack_start(dot, False, False, 0)
            row.pack_start(step_lbl, True, True, 0)
            box.pack_start(row, False, False, 0)
            step.row = row
            step.dot = dot
        page.pack_start(box, False, False, 0)

        # buttons row
        btnrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.build_buttons = getattr(self, "build_buttons", {})
        rom_btn = Gtk.Button(label="1 · Select your ROM…")
        rom_btn.connect("clicked", lambda _b: self.pick_rom(gid))
        btnrow.pack_start(rom_btn, False, False, 0)
        verify_btn = Gtk.Button(label="Verify ROM")
        verify_btn.connect("clicked", lambda _b: self.verify_rom(gid))
        btnrow.pack_start(verify_btn, False, False, 0)
        self.build_buttons[gid] = Gtk.Button(label="2 · Build my PS4 package")
        self.build_buttons[gid].get_style_context().add_class("suggested-action")
        self.build_buttons[gid].connect("clicked", lambda _b: self.start_build(gid))
        btnrow.pack_start(self.build_buttons[gid], False, False, 0)
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _b: self.cancel_build(gid))
        btnrow.pack_start(cancel_btn, False, False, 0)
        page.pack_start(btnrow, False, False, 6)

        # toolchain hint
        hint = Gtk.Label()
        hint.set_markup("<span size='small' foreground='#b45309'>Fresh machine? See the <b>Environment</b> tab's "
                        "<b>Fresh-machine setup</b> section — one click installs everything needed.</span>")
        hint.set_xalign(0)
        hint.set_line_wrap(True)
        page.pack_start(hint, False, False, 0)

        # output area
        self.pkg_labels = getattr(self, "pkg_labels", {})
        out_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        out_title = Gtk.Label()
        out_title.set_markup("<b>Output</b>")
        out_title.set_xalign(0)
        out_box.pack_start(out_title, False, False, 0)
        self.pkg_labels[gid] = Gtk.Label(label="—")
        self.pkg_labels[gid].set_xalign(0)
        out_box.pack_start(self.pkg_labels[gid], False, False, 0)
        page.pack_start(out_box, False, False, 0)

        # acceptance checkbox
        check = Gtk.CheckButton(label="I own this ROM dump and I only want to play it on my own PS4")
        check.set_active(self.opt(f"legal:{gid}", "accepted", "0") == "1")
        check.connect("toggled", lambda c: self.set_opt(f"legal:{gid}", "accepted", "1" if c.get_active() else "0"))
        page.pack_start(check, False, False, 0)

        # ROM display
        self.rom_labels = getattr(self, "rom_labels", {})
        self.rom_labels[gid] = Gtk.Label(label=("ROM: " + self.rom_candidates.get(gid, "not selected")))
        self.rom_labels[gid].set_xalign(0)
        page.pack_start(self.rom_labels[gid], False, False, 0)

        page.pack_start(self._ps4_upload_row(gid), False, False, 0)
        self.refresh_out(gid)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        inner = page
        inner.set_size_request(-1, -1)
        scrolled.add(inner)
        outer.pack_start(scrolled, True, True, 0)
        return outer

    def refresh_out(self, gid):
        if not hasattr(self, "pkg_labels"):
            return
        recipe = r4p.load_recipe(gid)
        want = recipe["ps4"]["pkg_name"].lower()
        pkgs = sorted((APP_DIR / "out").glob("*.pkg"))
        matching = [p for p in pkgs if want in p.name.lower()]
        if matching:
            self.pkg_labels[gid].set_text("Latest: " + matching[-1].name)
        else:
            self.pkg_labels[gid].set_text("No .pkg built yet (see the steps above)")

    # -------------------------------------------------- env page --
    def build_env_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_border_width(10)
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>Environment check</span>")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)

        desc = Gtk.Label()
        desc.set_markup("<span foreground='#666666'>What you need on this machine: a modern Linux with clang, cmake, ninja, "
                        "and the PS4 toolchain. The check runs the same diagnostics as the CLI "
                        "(<tt>r4p.py doctor</tt>). <b>Fresh machine? Press “ALL of the above” below to install everything.</b></span>")
        desc.set_xalign(0)
        desc.set_line_wrap(True)
        page.pack_start(desc, False, False, 0)

        btnrow = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        doctor_btn = Gtk.Button(label="Run environment check")
        doctor_btn.connect("clicked", lambda _b: self.run_doctor())
        btnrow.pack_start(doctor_btn, False, False, 0)
        deps_btn = Gtk.Button(label="Show install commands")
        deps_btn.connect("clicked", lambda _b: self.show_install_commands())
        btnrow.pack_start(deps_btn, False, False, 0)
        page.pack_start(btnrow, False, False, 0)

        setup_head = Gtk.Label()
        setup_head.set_markup("<b>Fresh-machine setup</b> — host packages, OpenOrbis, Mesa RADV, libnfs/libsmb2, sysroot")
        setup_head.set_xalign(0)
        page.pack_start(setup_head, False, False, 0)

        self.setup_btns = {}
        for label, script in (
            ("1. Install host packages (apt, needs sudo)", "setup-deps.sh"),
            ("2. Install OpenOrbis SDK (PacBrew packages, ~70 MB)", "setup-openorbis.sh"),
            ("3. Build PS4 sysroot (libc++ 21, ~10 min)", "build-sysroot.sh"),
            ("4. Clone libdrm headers", "clone-libdrm.sh"),
            ("5. Clone + patch Mesa 26.0.8 (RADV for PS4)", "setup-mesa.sh"),
            ("6. Build Mesa RADV (~15 min)", "build-mesa.sh"),
            ("7. Build SDL2 + FreeType for PS4", "../projects/hm64-ps4/scripts/build-deps.sh"),
            ("8. Build netfs libs (libnfs, libsmb2)", "build-netfs.sh"),
            ("ALL of the above (one button)", "setup-all.sh"),
        ):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            btn = Gtk.Button(label=label)
            btn.set_halign(Gtk.Align.START)
            btn.connect("clicked", self.run_setup_script, script)
            row.pack_start(btn, False, False, 0)
            page.pack_start(row, False, False, 0)
            self.setup_btns[script] = btn

        self.env_text = Gtk.TextView()
        self.env_text.set_editable(False)
        self.env_text.set_monospace(True)
        env_scroll = Gtk.ScrolledWindow()
        env_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        env_scroll.set_vexpand(True)
        env_scroll.add(self.env_text)
        page.pack_start(env_scroll, True, True, 0)
        return page

    def run_setup_script(self, _btn, script):
        script_path = Path(APP_DIR) / "scripts" / script
        if not script_path.exists():
            self.logf(f"  script not found: {script_path}")
            return
        self.logf(f"=== {script_path.name}: start")
        threading.Thread(target=self._setup_worker, args=(script_path,), daemon=True).start()

    def _setup_worker(self, script_path):
        env = dict(os.environ)
        env.setdefault("PS4_BUILD_ROOT", _default_root(None))
        env.setdefault("PS4_SYSROOT", f"{env['PS4_BUILD_ROOT']}/sysroot")
        proc = subprocess.Popen(["bash", str(script_path), env["PS4_BUILD_ROOT"]],
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace")
        out = []
        for line in iter(proc.stdout.readline, ""):
            out.append(line)
            self.logf("  " + line.rstrip("\n"))
        proc.wait()
        if proc.returncode != 0:
            self.logf(f"  FAILED: {proc.returncode}")
        else:
            self.logf("  done")

    def run_doctor(self):
        self.env_text.get_buffer().set_text("Running checks…\n")
        env_check = lambda: self._doctor_thread()
        threading.Thread(target=env_check, daemon=True).start()

    def _doctor_thread(self):
        proc = subprocess.Popen([sys.executable, str(APP_DIR / "r4p.py"), "doctor"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace")
        out = proc.stdout.read()
        proc.wait()
        GLib.idle_add(self.env_text.get_buffer().set_text, out)

    def show_install_commands(self):
        try:
            proc = subprocess.run([sys.executable, str(APP_DIR / "r4p.py"), "install-deps"],
                                  capture_output=True, text=True, timeout=15)
            text = proc.stdout
        except Exception as e:
            text = f"failed: {e}"
        self.env_text.get_buffer().set_text(text)

    # -------------------------------------------------- console page --
    def build_console_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_border_width(10)
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>Play it on your PS4</span>")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)

        steps = Gtk.Label()
        steps.set_markup(
            "1. On the PS4, enable GoldHEN and its <b>Package Installer</b> (jailbreak menu → Package Installer).\n"
            "2. Copy the .pkg to <tt>/data/pkg/</tt> on the PS4 — either with GoldHEN's FTP server\n"
            "    (<tt>ftp://&lt;ps4-ip&gt;:2121/data/pkg/</tt>, port 2121) or on a USB stick (exFAT).\n"
            "3. In <b>GoldHEN → Package Installer</b>, pick the package and install it.\n"
            "4. Launch the game from the PS4 home screen. Saves and logs live in <tt>/data/&lt;game&gt;</tt>.")
        steps.set_xalign(0)
        steps.set_line_wrap(True)
        page.pack_start(steps, False, False, 0)

        form = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        form.pack_start(Gtk.Label(label="PS4 IP:"), False, False, 0)
        self.console_host = Gtk.Entry()
        self.console_host.set_text(self.opt("console", "host", "192.168.0.90"))
        self.console_host.connect("changed", lambda e: self.set_opt("console", "host", e.get_text()))
        form.pack_start(self.console_host, True, True, 0)
        upload_btn = Gtk.Button(label="Upload latest .pkg via FTP")
        upload_btn.connect("clicked", lambda _b: self.upload_latest())
        form.pack_start(upload_btn, False, False, 0)
        page.pack_start(form, False, False, 0)

        open_btn = Gtk.Button(label="Open the output folder")
        open_btn.connect("clicked", lambda _b: subprocess.Popen(["xdg-open", str(APP_DIR / "out")]))
        page.pack_start(open_btn, False, False, 0)
        return page

    def _ps4_upload_row(self, gid):
        """A row with the PS4 IP entry and a button that FTP-uploads the latest matching .pkg."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_border_width(2)
        lbl = Gtk.Label()
        lbl.set_markup("<b>PS4 IP:</b>")
        row.pack_start(lbl, False, False, 0)
        entry = Gtk.Entry()
        entry.set_placeholder_text("192.168.0.90")
        entry.set_text(self.opt("console", "host", "192.168.0.90"))
        entry.set_width_chars(16)
        entry.set_tooltip_text("Your PS4's IP on the LAN — e.g. 192.168.0.90 (FTP port 2121 by default)")
        entry.connect("changed", lambda e: self.set_opt("console", "host", e.get_text()))
        row.pack_start(entry, False, False, 0)
        test = Gtk.Button(label="Ping")
        test.set_tooltip_text("Test reachability (ping -c 2 <IP>)")
        test.connect("clicked", lambda _b: self._ping_ip(entry.get_text()))
        row.pack_start(test, False, False, 0)
        upload = Gtk.Button(label="Upload .pkg now")
        upload.set_tooltip_text("Upload the newest matching .pkg in out/ to the PS4's /data/pkg over FTP")
        upload.connect("clicked", lambda _b: self._upload_game_pkg(gid, entry.get_text()))
        row.pack_start(upload, False, False, 0)
        box.pack_start(row, False, False, 0)

        auto = Gtk.CheckButton(label="Auto-upload the package to the console when the build finishes")
        auto.set_tooltip_text("When a build finishes successfully, the fresh .pkg is FTP'd to the PS4's /data/pkg right away (GoldHEN → Package Installer to install).")
        auto.set_active(self.opt("console", "auto_upload", "0") == "1")
        auto.connect("toggled", lambda c: self.set_opt("console", "auto_upload", "1" if c.get_active() else "0"))
        box.pack_start(auto, False, False, 0)
        return box

    def auto_upload_if_enabled(self, gid):
        if self.opt("console", "auto_upload", "0") != "1":
            return
        host = self.opt("console", "host", "").strip()
        if not host:
            self.logf("  auto-upload skipped: no PS4 IP configured")
            return
        self.logf(f"  auto-upload is on — sending the package to {host}…")
        self._upload_game_pkg(gid, host)

    def _ping_ip(self, host):
        host = host.strip()
        if not host:
            self.logf("  no PS4 IP configured")
            return
        self.logf(f"  ping {host} ×2…")
        try:
            proc = subprocess.run(["ping", "-c", "2", "-W", "1", host],
                                  capture_output=True, text=True, timeout=5)
            self.logf(proc.stdout.strip())
            if proc.returncode != 0:
                self.logf(proc.stderr.strip() or "  ping failed")
        except Exception as e:
            self.logf(f"  ping failed: {e}")

    def _upload_game_pkg(self, gid, host):
        host = host.strip()
        if not host:
            self.logf("  no PS4 IP configured")
            return
        recipe = r4p.load_recipe(gid)
        pkg_name = recipe["ps4"]["pkg_name"]
        pkgs = sorted((APP_DIR / "out").glob("*.pkg"), key=lambda p: p.stat().st_mtime)
        matching = [p for p in pkgs if pkg_name.lower() in p.name.lower()]
        if not matching:
            self.logf(f"  no .pkg for {pkg_name} in out/ — build it first")
            return
        pkg = matching[-1]
        self.logf(f"  uploading {pkg.name} to {host} (/data/pkg)…")
        threading.Thread(target=self._upload_thread, args=(pkg, host), daemon=True).start()

    def upload_latest(self):
        host = self.console_host.get_text().strip() if hasattr(self, "console_host") else self.opt("console", "host", "")
        if not host:
            self.logf("  no PS4 IP configured")
            return
        pkgs = sorted((APP_DIR / "out").glob("*.pkg"), key=lambda p: p.stat().st_mtime)
        if not pkgs:
            self.logf("  no .pkg in out/ yet — build a game first")
            return
        # Upload the newest .pkg; if a game page is visible, prefer that game's package.
        gid = self._current_game_id()
        if gid:
            self._upload_game_pkg(gid, host)
        else:
            pkg = pkgs[-1]
            self.logf(f"  uploading {pkg.name} to {host}…")
            threading.Thread(target=self._upload_thread, args=(pkg, host), daemon=True).start()

    def _current_game_id(self):
        child = self.stack.get_visible_child_name()
        return child[len("game-"):] if child and child.startswith("game-") else None

    def _upload_thread(self, pkg, host):
        url = f"ftp://{host}:{os.environ.get('PS4_FTP_PORT', '2121')}/data/pkg/"
        try:
            proc = subprocess.run(["curl", "-sS", "-T", str(pkg), url],
                                  capture_output=True, text=True, timeout=1800)
            if proc.returncode == 0:
                text = f"  uploaded {pkg.name} — check GoldHEN → Package Installer on the PS4\n"
            else:
                text = f"  FTP upload failed (curl exit {proc.returncode}):\n{proc.stderr}\n"
        except Exception as e:
            text = f"  FTP upload failed: {e}\n"
        GLib.idle_add(self.logf, text)

    # -------------------------------------------------- settings page --
    def build_settings_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_border_width(10)
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>Settings</span>")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)

        self.root_entries = getattr(self, "root_entries", {})
        for gid in r4p.list_games():
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            lbl = Gtk.Label()
            lbl.set_markup(f"<b>{GLib.markup_escape_text(r4p.load_recipe(gid)['title'])} build root</b>")
            lbl.set_xalign(0)
            row.pack_start(lbl, False, False, 0)
            entry = Gtk.Entry()
            entry.set_text(self.build_root_for(gid))
            entry.set_width_chars(36)
            entry.connect("changed", lambda e, g=gid: self.set_opt(f"paths:{g}", "build_root", e.get_text()))
            self.root_entries[gid] = entry
            row.pack_start(entry, True, True, 0)
            browse = Gtk.Button(label="Browse…")
            browse.connect("clicked", lambda _b, g=gid: self.pick_folder(g))
            row.pack_start(browse, False, False, 0)
            page.pack_start(row, False, False, 0)

        note = Gtk.Label()
        note.set_markup('<span foreground="#666666">The build root holds the cloned recompiler project, your staged ROM, '
                        'and everything the build produces (a few GB). Default: <tt>~/ps4-build</tt> for both games.</span>')
        note.set_xalign(0)
        note.set_line_wrap(True)
        page.pack_start(note, False, False, 0)

        reset_btn = Gtk.Button(label="Reset settings")
        reset_btn.connect("clicked", self.reset_settings)
        page.pack_start(reset_btn, False, False, 0)
        return page

    def pick_folder(self, gid):
        dialog = Gtk.FileChooserNative.new("Choose build root", self.win,
                                           Gtk.FileChooserAction.SELECT_FOLDER,
                                           "Select", "Cancel")
        dialog.connect("response", self._folder_response, gid)
        dialog.show()

    def _folder_response(self, dialog, response_id, gid):
        if response_id == Gtk.ResponseType.ACCEPT:
            path = dialog.get_filename()
            self.set_opt(f"paths:{gid}", "build_root", path)
            if hasattr(self, "root_entries") and gid in self.root_entries:
                self.root_entries[gid].set_text(path)
            self.logf(f"  build root for {gid}: {path}")
        dialog.destroy()

    def reset_settings(self, _btn):
        if SETTINGS_FILE.exists():
            SETTINGS_FILE.unlink()
        self.settings = configparser.ConfigParser()
        self.logf("  settings reset")

    # -------------------------------------------------- about page --
    def build_about_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        page.set_border_width(10)
        title = Gtk.Label()
        title.set_markup("<span size='x-large' weight='bold'>About recomp4ps4</span>")
        title.set_xalign(0)
        page.pack_start(title, False, False, 0)
        body = Gtk.Label()
        body.set_markup(
            "recomp4ps4 turns a static recompiler project plus <b>your own ROM dump</b> into an installable "
            "PS4 package. It never downloads, includes or redistributes game content: what you build is "
            "yours, for your console, for personal use.\n\n"
            "<b>Games</b>\n"
            "• Harvest Moon 64 — Harvest Moon 64: Recompiled (upstream, submodules) → PS4 port\n"
            "• Mario Party 3 — mario-party-3-recomp → PS4 port\n\n"
            "<b>What this app cannot do</b>\n"
            "• It cannot invent a recompilation for a game with no community project.\n"
            "• The PS4 toolchain is required — but one click builds it (Environment tab, “Fresh-machine setup”).\n"
            "• The first build of any game is never plug-and-play: expect to read logs, fix a path, retry.\n\n"
            "<b>Useful docs</b>\n"
            "• <tt>python3 r4p.py read hm64:readme</tt> and <tt>… mp3:readme</tt> — upstream build docs\n"
            "• Each project's <tt>PORTING.md</tt> — the hand-porting checklist")
        body.set_xalign(0)
        body.set_line_wrap(True)
        page.pack_start(body, False, False, 0)
        return page

    # -------------------------------------------------- actions --
    def on_row_selected(self, _list, row):
        if row is not None:
            self.stack.set_visible_child_name(f"game-{row.game_id}")

    def pick_rom(self, gid):
        dialog = Gtk.FileChooserDialog(
            title="Select your ROM dump",
            transient_for=self.win,
            action=Gtk.FileChooserAction.OPEN)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Select", Gtk.ResponseType.ACCEPT)
        rom_dir = APP_DIR / "projects" / "roms"
        if rom_dir.exists():
            dialog.set_current_folder(str(rom_dir))
        filt = Gtk.FileFilter()
        filt.set_name("N64 ROMs (*.z64)")
        filt.add_pattern("*.z64")
        filt.add_pattern("*.rom")
        dialog.add_filter(filt)
        response = dialog.run()
        path = dialog.get_filename() if response == Gtk.ResponseType.ACCEPT else None
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT and path:
            self._rom_response(path, gid)

    def _rom_response(self, path, gid):
        self.rom_candidates[gid] = path
        self.rom_labels[gid].set_text(f"ROM: {path}")
        self.logf(f"  ROM selected: {path}")
        want = r4p.load_recipe(gid)["rom"]["sha1"]
        digest = r4p.sha1_of(Path(path)) if Path(path).exists() else None
        if digest is None:
            self.logf("  file is missing")
        elif digest == want:
            self.logf("  SHA-1 matches — this is the right dump")
        else:
            self.logf(f"  SHA-1 does NOT match (got {digest})")

    def verify_rom(self, gid):
        path = self.rom_candidates.get(gid)
        recipe = r4p.load_recipe(gid)
        if not path or not Path(path).exists():
            self.logf("  no ROM selected — pick one first")
            return
        digest = r4p.sha1_of(Path(path))
        want = recipe["rom"]["sha1"]
        if digest == want:
            self.logf(f"  OK: {digest} (region {recipe['rom']['region']}, {r4p.human(Path(path).stat().st_size)})")
        else:
            self.logf(f"  MISMATCH: got {digest}, expected {want}")
            self.logf("  This is not the dump this game needs (probably a different region).")

    def start_build(self, gid):
        if self.opt(f"legal:{gid}", "accepted", "0") != "1":
            self.logf("  please tick the ROM-ownership checkbox on this page first")
            return
        pipeline = self.pipelines[gid]
        pipeline.cancel = threading.Event()
        for step in pipeline.steps:
            step.reset()
            step.dot.set_label("○")
            step.row.set_tooltip_text(None)
        self.build_buttons[gid].set_sensitive(False)
        thread = threading.Thread(target=self.build_worker, args=(gid,), daemon=True)
        thread.start()

    def cancel_build(self, gid):
        self.pipelines[gid].cancel.set()
        self.logf("  cancel requested — waiting for the current step to stop…")

    def build_worker(self, gid):
        pipeline = self.pipelines[gid]
        rom_src = self.rom_candidates.get(gid)
        for step in pipeline.steps:
            if pipeline.cancel.is_set():
                self.logf("  cancelled")
                break
            GLib.idle_add(self.step_state, step, "running", "")
            try:
                ok, detail = pipeline.run_step(step, rom_src)
            except Exception as e:
                ok, detail = False, str(e)
            GLib.idle_add(self.step_state, step, "ok" if ok else "failed", detail)
            if not ok:
                self.logf(f"  step failed: {step.title} — {detail}")
                break
            if step.key == "package" and ok:
                self.auto_upload_if_enabled(gid)
        else:
            self.logf("  ALL DONE — your package should be in out/")
        GLib.idle_add(self._build_finished, gid)

    def step_state(self, step, state, detail):
        step.state = state
        step.detail = detail
        step.dot.set_label({"pending": "○", "running": "▸", "ok": "✔", "failed": "✘"}[state])
        return False

    def _build_finished(self, gid):
        self.build_buttons[gid].set_sensitive(True)
        self.refresh_out(gid)
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        failures = []
        for gid in r4p.list_games():
            recipe = r4p.load_recipe(gid)
            print(f"{gid}: {recipe['title']}")
            for key, ok in (
                ("recipe loads", True),
                ("ROM sha1 known", bool(recipe["rom"]["sha1"])),
                ("ps4 title_id", bool(recipe["ps4"]["title_id"])),
                ("build root default", bool(_default_root(gid))),
            ):
                print(f"    {key}: {'ok' if ok else 'FAIL'}")
                if not ok:
                    failures.append(f"{gid}:{key}")
        for gid in r4p.list_games():
            root = Path(_default_root(gid))
            ok = _resolve(str(root / "src")).exists()
            print(f"{gid}: default root {root} -> {'exists' if ok else 'missing'}")
        p = APP_DIR / "projects" / "roms"
        print(f"roms dir: {'exists' if p.exists() else 'missing'}")
        return 1 if failures else 0

    win = AppWindow()
    win.win.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
