# Credits and notices

recomp4ps4 is an orchestrator and a PS4 port layer built on a lot of other
people's work. This file credits the projects it stands on, along with their
licenses. Upstream licenses apply to their components; recomp4ps4's own code
is GPL-3.0 (see LICENSE).

## The recompilation pipeline

- **[HarvestMoon64Recomp](https://github.com/HarvestMoon64Recomp/HarvestMoon64Recomp)** —
  the Harvest Moon 64: Recompiled project (GPL-3.0). The game's static
  recompilation this port targets; its `host/` tree is what the PS4 build compiles.
- **[mario-party-3-recomp](https://github.com/n64hub/mario-party-3-recomp)** —
  the Mario Party 3 recompilation project (GPL-3.0). Same role for Mario Party 3.
- **[N64Recomp](https://github.com/N64Recomp/N64Recomp)** and
  **[N64ModernRuntime](https://github.com/N64Recomp/N64ModernRuntime)** —
  the static recompiler and the runtime (librecomp, ultramodern). N64Recomp
  is MIT; the runtime is GPL-3.0. `projects/*/patches/n64modernruntime-ps4.patch`
  carries the PS4 sections for the runtime (GPL-3.0 applies).
- **[sljit](https://github.com/zherczeg/sljit)** (BSD-2-Clause) — dynamic code
  generation used for mods.
- **[RT64](https://github.com/rt64/rt64)** (MIT) — the renderer N64 games use.
- **[RecompFrontend](https://github.com/N64Recomp/RecompFrontend)** — the
  launcher/menus framework used by the recomp projects.
- **[CBFD-Recompiled](https://github.com/sciaschi/CBFD-Recompiled)** (MIT) —
  the structure and flow this port layer was prototyped from (Conker's Bad Fur
  Day: Recompiled).

## The PS4 side

- **[Conker-PS4](https://github.com/iHaiDeeZ/Conker-PS4)** (iHaiDeeZ) — the PS4
  port structure, the pkg/fake-pkg packaging flow, the `hn`-style hardening
  approach and the PS4 boot-trace debugging this project grew out of.
- **[HENkaku-PS4](https://github.com/iHaiDeeZ/HENkaku-PS4)** and
  **[G-Diffuser-PS4](https://github.com/iHaiDeeZ/G-Diffuser-PS4)** (ShiroKlein) —
  the PS4 runtime: the heap, the shadow patches, the VideoOut presentation path
  and the WSI used for the Vulkan surface on PS4. `ps4/ps4_wsi.cpp` and the
  `port/` layer follow their approach.
- **[Mesa](https://mesa3d.org)** (MIT) — the RADV Vulkan driver, ported to the
  PS4's GNM GPU by iHaiDeeZ (Crema); `port/mesa/ac_ps4_drm.c` is that port's
  winsys. Mesa is patched by `projects/hm64-ps4/patches/mesa/mesa-ps4.patch`
  (identical for mp3).
- **[SDL2](https://libsdl.org)** (zlib license) — the game engine's core
  services; `ps4/sdl2/SDL_ps4audio.c` is the port's PS4 audio driver.
- **[FreeType](https://freetype.org)** (FTL/FreeType License) — RmlUi's font engine.
- **[OpenOrbis](https://github.com/OpenOrbis)** — the PS4 toolchain
  (crt, `link.x`, `create-fself`, `PkgTool`). The toolchain is a separate
  project; recomp4ps4 uses PacBrew's prebuilt packages of it.
- **[libnfs](https://github.com/sahlberg/libnfs)** and
  **[libsmb2](https://github.com/sahlberg/libsmb2)** (LGPL-2.1) — user-space
  NFS and SMB clients for the game's `/net` mounts.
- **[dlmalloc](https://gee.cs.oswego.edu/dl/html/malloc.html)** (public domain,
  Doug Lea) — the heap used inside the PS4 app.

## What this repo is NOT

- **No game content.** No ROMs, no recompiled code, no extracted assets, no
  game-specific data files. The game packages you build contain code derived
  from your own dump; the built `.pkg` files are for your own PS4 only and
  must never be shared — that would be redistributing derivative works of the
  games. They are `.gitignore`d, as are ROMs.
- **No Sony files.** The PS4's system libraries (`libSce*`) and the game's own
  content are never included; the packages you build run on your console with
  its own system software.
- Not affiliated with Nintendo, Rare or any other rights holder of the games.

## Trademarks

Harvest Moon, Mario Party, their characters and imagery belong to their
respective owners. The names are used descriptively only, to say which games
this tool can build for your own console.
