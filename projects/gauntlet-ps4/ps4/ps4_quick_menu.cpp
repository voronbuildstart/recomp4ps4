// Gauntlet Legends: Recompiled for PS4: the DualShock 4's quick menu (L3 + R3).
//
// Gauntlet's host has no in-emulator quick menu (the in-game UI is the menu, and the pad's buttons are
// the game's own): the combo that opens it is watched in ps4_pad.cpp's virtual joystick, and the
// request is drained here on the host's frame update. The menu's switches live in the port's ps4.ini
// (ps4_setting_get).

#include "ps4_platform.h"
#include "ps4_cheats.h"
#include <cstdio>

extern "C" void ps4_quick_menu_update(void) {
    // Gauntlet has no in-emulator menu, so the shared cheat engine draws a small overlay into the
    // swapchain at presentation time (ps4_wsi.cpp). The same L3 + R3 request opens and closes it.
    ps4_cheats_apply();
    ps4_cheat_menu_update();
}
