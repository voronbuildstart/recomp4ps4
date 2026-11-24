// Harvest Moon 64's published GameShark codes (single unconditional byte/halfword writes).
#include "ps4_cheats.h"

extern "C" void ps4_cheats_init(void) {
    static const Ps4CheatWrite money[] = { { 0x811FD60E, 0xFFFF, 2 } };
    static const Ps4CheatWrite stamina[] = { { 0x80189060, 0x00FF, 1 } };
    static const Ps4CheatWrite chicken_feed[] = { { 0x80237411, 0x005C, 1 } };
    static const Ps4CheatWrite lumber[] = { { 0x80189E50, 0x00FF, 1 } };
    static const Ps4CheatWrite watering_can[] = { { 0x8016FBCD, 0x0004, 1 } };
    static const Ps4CheatWrite fodder[] = { { 0x81180714, 0x0063, 2 } };

    ps4_cheats_add("Infinite Money", money, 1);
    ps4_cheats_add("Max Stamina", stamina, 1);
    ps4_cheats_add("Chicken Feed", chicken_feed, 1);
    ps4_cheats_add("Max Lumber", lumber, 1);
    ps4_cheats_add("Watering Can", watering_can, 1);
    ps4_cheats_add("Max Fodder", fodder, 1);
}
