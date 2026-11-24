// Shared GameShark-style cheat engine + fallback overlay menu for the N64 PS4 ports.
//
// Only unconditional single writes are supported: 80/A0 (byte) and 81/A1 (halfword). Master,
// enabler, button and conditional codes are deliberately left out. Cheats are applied every
// frame from ps4_quick_menu_update(), so they survive the game overwriting the address (and they
// do not need a pause hook). Enabled flags live in the port's ps4.ini as cheat0, cheat1, ...
//
// HM64 and MP3 render their own recompui quick menu and only use the engine/table API. Kirby and
// Gauntlet have no in-app UI, so those ports also call the fallback menu + overlay hook: it opens
// with L3+R3 and is drawn into the swapchain image at presentation time.

#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t address;   // N64 virtual address, e.g. 0x80189060
    uint16_t value;     // the value from the GameShark code
    uint8_t width;      // 1 or 2 bytes
} Ps4CheatWrite;

void ps4_cheats_reset(void);
void ps4_cheats_add(const char *name, const Ps4CheatWrite *writes, int count);

int ps4_cheats_count(void);
const char *ps4_cheats_name(int index);
int ps4_cheats_enabled(int index);
void ps4_cheats_toggle(int index);

// Writes every enabled cheat to RDRAM. Called once per host frame.
void ps4_cheats_apply(void);

// Defined by each game's port; registers that game's cheat table.
void ps4_cheats_init(void);

// Fallback menu (Kirby/Gauntlet): input, state and a presentation-time text overlay.
void ps4_cheat_menu_update(void);
int ps4_cheat_menu_active(void);
void ps4_cheat_menu_draw(uint8_t *pixels, uint32_t width, uint32_t height, uint32_t pitch, int bgra);

#ifdef __cplusplus
}
#endif
