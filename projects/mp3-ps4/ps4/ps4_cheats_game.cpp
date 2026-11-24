// Mario Party 3's published GameShark codes: coins and stars for each of the four characters.
// The original F1 master code is intentionally omitted: the engine writes guest RAM directly.
#include "ps4_cheats.h"

extern "C" void ps4_cheats_init(void) {
    static const Ps4CheatWrite p1_coins[] = { { 0x810D1112, 0x0063, 2 } };
    static const Ps4CheatWrite p1_stars[] = { { 0x800D1116, 0x0063, 1 } };
    static const Ps4CheatWrite p2_coins[] = { { 0x810D114A, 0x0063, 2 } };
    static const Ps4CheatWrite p2_stars[] = { { 0x800D114E, 0x0063, 1 } };
    static const Ps4CheatWrite p3_coins[] = { { 0x810D1182, 0x0063, 2 } };
    static const Ps4CheatWrite p3_stars[] = { { 0x800D1186, 0x0063, 1 } };
    static const Ps4CheatWrite p4_coins[] = { { 0x810D11BA, 0x0063, 2 } };
    static const Ps4CheatWrite p4_stars[] = { { 0x800D11BE, 0x0063, 1 } };

    ps4_cheats_add("P1: 99 Coins", p1_coins, 1);
    ps4_cheats_add("P1: 99 Stars", p1_stars, 1);
    ps4_cheats_add("P2: 99 Coins", p2_coins, 1);
    ps4_cheats_add("P2: 99 Stars", p2_stars, 1);
    ps4_cheats_add("P3: 99 Coins", p3_coins, 1);
    ps4_cheats_add("P3: 99 Stars", p3_stars, 1);
    ps4_cheats_add("P4: 99 Coins", p4_coins, 1);
    ps4_cheats_add("P4: 99 Stars", p4_stars, 1);
}
