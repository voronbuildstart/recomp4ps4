// Gauntlet Legends' published GameShark codes (single unconditional byte/halfword writes).
// The EE/DD/CC enable codes are intentionally omitted: this engine writes guest RAM directly.
#include "ps4_cheats.h"

extern "C" void ps4_cheats_init(void) {
    static const Ps4CheatWrite health[] = {
        { 0x810C5C54, 0x0000, 2 },
        { 0x810C5C56, 0x270F, 2 },
    };
    static const Ps4CheatWrite max_stats[] = {
        { 0x810C5C04, 0x0000, 2 }, { 0x810C5C06, 0xFFFF, 2 },
        { 0x810C5C14, 0x0000, 2 }, { 0x810C5C16, 0xFFFF, 2 },
        { 0x810C5C24, 0x0000, 2 }, { 0x810C5C26, 0xFFFF, 2 },
        { 0x810C5C34, 0x0000, 2 }, { 0x810C5C36, 0xFFFF, 2 },
    };
    static const Ps4CheatWrite five_way[] = { { 0x800FD198, 0x0200, 1 } };
    static const Ps4CheatWrite rapid_fire[] = { { 0x800FD19A, 0x1000, 1 } };
    static const Ps4CheatWrite money_p2[] = { { 0x810C60D6, 0xFFFF, 2 } };

    ps4_cheats_add("Infinite Health", health, 2);
    ps4_cheats_add("Max Stats P1", max_stats, 8);
    ps4_cheats_add("5-Way Shot", five_way, 1);
    ps4_cheats_add("Rapid Fire", rapid_fire, 1);
    ps4_cheats_add("P2: Infinite Money", money_p2, 1);
}
