// Kirby 64's published GameShark codes (single unconditional byte/halfword writes).
#include "ps4_cheats.h"

extern "C" void ps4_cheats_init(void) {
    static const Ps4CheatWrite lives[] = { { 0x800D6F4F, 0x0009, 1 } };
    static const Ps4CheatWrite health[] = { { 0x810D6E50, 0x40C0, 2 } };
    static const Ps4CheatWrite fly[] = { { 0x8112E7DE, 0x00F0, 2 } };
    static const Ps4CheatWrite invincible[] = { { 0x800E7CE3, 0x0005, 1 } };

    ps4_cheats_add("Infinite Lives", lives, 1);
    ps4_cheats_add("Infinite Health", health, 1);
    ps4_cheats_add("Fly Forever", fly, 1);
    ps4_cheats_add("Invincible", invincible, 1);
}
