# recomp4ps4

Build N64 static-recompilation ports (**Harvest Moon 64** and **Mario Party 3**)
as installable packages for a **GoldHEN-jailbroken PS4**.

It is an orchestrator for a pipeline that is already proven to work —
[iHaiDeeZ/Conker-PS4](https://github.com/iHaiDeeZ/Conker-PS4) runs
*N64Recomp + N64ModernRuntime + RT64 (Vulkan via Mesa RADV)* natively on a
jailbroken PS4. This app retargets that port layer to other games that already
have finished recomp projects, and automates every step around them.

```
your ROM dump ──► verify ──► PC build (validation) ──► PS4 workspace ──► .pkg ──► GoldHEN
                  (r4p rom)      (r4p pc)                (r4p ps4)      (r4p ps4 --build)  (r4p install)
```

## What it does / does not do

**Automated:** a full fresh-machine setup (apt, PacBrew, Mesa, sysroot), cloning the community recomp projects, ROM verification (region/size/SHA-1), PC builds, generating the PS4 port workspace from the Conker-PS4 template (string retargeting + a porting checklist), OpenOrbis `.pkg` packaging, install instructions + FTP push.

**Not automated (impossible):** creating a recomp for a game that has none.
Recipes point at existing, finished projects:

| Game | Upstream | ROM required |
|---|---|---|
| `hm64` | [HarvestMoon64Recomp](https://github.com/HarvestMoon64Recomp/HarvestMoon64Recomp) | North American `.z64` |
| `mp3`  | [n64hub/mario-party-3-recomp](https://github.com/n64hub/mario-party-3-recomp) | USA `.z64`, 32 MiB, SHA-1 `6beb80ff…d8259` |

Also not automated: the first PS4 build of a game. The workspace generator
copies the template and retargets it, but wiring a new game's recomp output
into the PS4 build needs eyes on both repos — the workspace contains
`PORTING.md` with the exact checklist. Expect hands-on iteration; logs on the
console (`/data/<game>/`) make it tractable.

## Quick start

Clone this repo somewhere writable and run the GUI:

```bash
python3 r4p.py gui
```

Bring your ROM dump; everything else downloads on first use. The **Environment** tab's *Fresh-machine setup* section installs the full toolchain, source by source (apt packages → PacBrew OpenOrbis → Mesa → sysroot → SDL2/FreeType → netfs). One *ALL of the above* button runs it all.

## Command-line fresh-machine setup

```bash
bash scripts/setup-all.sh ~/ps4-build # everything, ~30 min on a fast machine
```

then `python3 r4p.py ps4 hm64 --build` (or `mp3`) to clone, recompile, build and package; `python3 r4p.py install hm64 --push <ps4-ip>` to FTP the package to the console. `python3 r4p.py doctor` diagnoses a half-set-up machine.

## PS4-side requirements

- **GoldHEN** with its **Package Installer** (this is what loads the `.pkg`)
- FTP server enabled (GoldHEN menu), or a USB stick (exFAT)
- PS4 Pro: enable **Boost Mode** for extra headroom

## Legal

The app ships no ROMs, no recompiled game code, no packages containing game
data. Packages you build contain **your** ROM → personal use only, not for
distribution. Only dump and port games you own.

## Sharing this repo

If you publish this, keep it clean: ROMs (`projects/roms/`), built packages
(`out/`) and the recompiled game code are all gitignored — never commit them.
A package contains code derived from the game and is **not** yours to
redistribute; the tool and the port layer are. The SHA-1s in `games/*.json`
identify ROMs by fingerprint only and contain no game data.

## Layout

```
r4p.py          the CLI (Python 3, stdlib only)
gui/            the GTK3 GUI (python3 + PyGObject)
games/*.json    per-game recipes: repo, ROM spec, build steps, PS4 retarget map
scripts/        the fresh-machine setup scripts (deps, sysroot, Mesa, SDL2, netfs)
projects/       cloned upstreams + PS4 port workspaces (created as you go)
out/            built .pkg files
```

## License

GPL-3.0 — the port layer derives from Conker-PS4 and the recomp projects, which
are GPL-3.0. See `NOTICE.md` for the full credits (upstream projects keep their
own licenses). This repo contains no game content.
