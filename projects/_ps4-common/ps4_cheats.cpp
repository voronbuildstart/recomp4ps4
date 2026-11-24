#include "ps4_cheats.h"

#include "ps4_platform.h"

#include <orbis/Pad.h>

#include <atomic>
#include <cstdio>
#include <cstring>

namespace {

constexpr int kMaxCheats = 32;
constexpr int kMaxWrites = 8;

struct Cheat {
    const char *name = nullptr;
    Ps4CheatWrite writes[kMaxWrites];
    int count = 0;
};

Cheat g_cheats[kMaxCheats];
int g_count = 0;
bool g_applied = false;

// Fallback menu state (only used by ports without recompui).
std::atomic<bool> g_menu_open{ false };
std::atomic<int> g_selected{ 0 };
uint32_t g_previous_buttons = 0;

void store_be(uint8_t *address, uint16_t value, int width) {
    if (width == 1) {
        address[0] = static_cast<uint8_t>(value);
    } else {
        // N64 is big-endian; the host is little-endian.
        address[0] = static_cast<uint8_t>(value >> 8);
        address[1] = static_cast<uint8_t>(value & 0xFF);
    }
}

uint8_t *guest_address(uint32_t address) {
    uint8_t *base = static_cast<uint8_t *>(ps4_vm_base());
    if (base == nullptr)
        return nullptr;
    // N64 virtual addresses: kseg0 (0x80000000) and kseg1 (0xA0000000) both map to physical RAM by
    // stripping the top 3 bits. GameShark codes use 0x80xxxxxx and 0x81xxxxxx for the same RDRAM.
    if ((address & 0xE0000000u) == 0x80000000u || (address & 0xE0000000u) == 0xA0000000u)
        address &= 0x1FFFFFFFu;
    // Physical addresses (0x0000...0x7FFFFF) are the same RAM.
    if (address < 0x00800000u)
        return base + address;
    return nullptr;
}

// --- tiny 5x7 bitmap font -------------------------------------------------------
// Bit 0x10 is the leftmost pixel of a row. Only the characters used by the menu
// are present; anything else is a space.

#define GLYPH(name, ...) static const uint8_t GLYPH_##name[7] = { __VA_ARGS__ }
GLYPH(SPACE, 0, 0, 0, 0, 0, 0, 0);
GLYPH(A, 0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11);
GLYPH(B, 0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E);
GLYPH(C, 0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E);
GLYPH(D, 0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E);
GLYPH(E, 0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F);
GLYPH(F, 0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10);
GLYPH(G, 0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F);
GLYPH(H, 0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11);
GLYPH(I, 0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E);
GLYPH(J, 0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C);
GLYPH(K, 0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11);
GLYPH(L, 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F);
GLYPH(M, 0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11);
GLYPH(N, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11);
GLYPH(O, 0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E);
GLYPH(P, 0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10);
GLYPH(Q, 0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D);
GLYPH(R, 0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11);
GLYPH(S, 0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E);
GLYPH(T, 0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04);
GLYPH(U, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E);
GLYPH(V, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04);
GLYPH(W, 0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11);
GLYPH(X, 0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11);
GLYPH(Y, 0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04);
GLYPH(Z, 0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F);
GLYPH(N0, 0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E);
GLYPH(N1, 0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E);
GLYPH(N2, 0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F);
GLYPH(N3, 0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E);
GLYPH(N4, 0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02);
GLYPH(N5, 0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E);
GLYPH(N6, 0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E);
GLYPH(N7, 0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08);
GLYPH(N8, 0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E);
GLYPH(N9, 0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C);
GLYPH(COLON, 0x00, 0x04, 0x04, 0x00, 0x04, 0x04, 0x00);
GLYPH(SLASH, 0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10);
GLYPH(PLUS, 0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00);
GLYPH(MINUS, 0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00);
GLYPH(DOT, 0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C);
GLYPH(LPAREN, 0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02);
GLYPH(RPAREN, 0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08);
GLYPH(BANG, 0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04);
GLYPH(GREATER, 0x10, 0x08, 0x04, 0x02, 0x04, 0x08, 0x10);
#undef GLYPH

const uint8_t *glyph(char c) {
    if (c >= 'a' && c <= 'z')
        c = static_cast<char>(c - 'a' + 'A');
    switch (c) {
    case 'A': return GLYPH_A;
    case 'B': return GLYPH_B;
    case 'C': return GLYPH_C;
    case 'D': return GLYPH_D;
    case 'E': return GLYPH_E;
    case 'F': return GLYPH_F;
    case 'G': return GLYPH_G;
    case 'H': return GLYPH_H;
    case 'I': return GLYPH_I;
    case 'J': return GLYPH_J;
    case 'K': return GLYPH_K;
    case 'L': return GLYPH_L;
    case 'M': return GLYPH_M;
    case 'N': return GLYPH_N;
    case 'O': return GLYPH_O;
    case 'P': return GLYPH_P;
    case 'Q': return GLYPH_Q;
    case 'R': return GLYPH_R;
    case 'S': return GLYPH_S;
    case 'T': return GLYPH_T;
    case 'U': return GLYPH_U;
    case 'V': return GLYPH_V;
    case 'W': return GLYPH_W;
    case 'X': return GLYPH_X;
    case 'Y': return GLYPH_Y;
    case 'Z': return GLYPH_Z;
    case '0': return GLYPH_N0;
    case '1': return GLYPH_N1;
    case '2': return GLYPH_N2;
    case '3': return GLYPH_N3;
    case '4': return GLYPH_N4;
    case '5': return GLYPH_N5;
    case '6': return GLYPH_N6;
    case '7': return GLYPH_N7;
    case '8': return GLYPH_N8;
    case '9': return GLYPH_N9;
    case ':': return GLYPH_COLON;
    case '/': return GLYPH_SLASH;
    case '+': return GLYPH_PLUS;
    case '-': return GLYPH_MINUS;
    case '.': return GLYPH_DOT;
    case '(': return GLYPH_LPAREN;
    case ')': return GLYPH_RPAREN;
    case '!': return GLYPH_BANG;
    case '>': return GLYPH_GREATER;
    default: return GLYPH_SPACE;
    }
}

struct Color { uint8_t r, g, b; };

void put_pixel(uint8_t *pixels, uint32_t width, uint32_t height, uint32_t pitch,
               int x, int y, int bgra, Color color) {
    if (x < 0 || y < 0 || static_cast<uint32_t>(x) >= width || static_cast<uint32_t>(y) >= height)
        return;
    uint8_t *p = pixels + static_cast<uint32_t>(y) * pitch + static_cast<uint32_t>(x) * 4;
    if (bgra) {
        p[0] = color.b; p[1] = color.g; p[2] = color.r;
    } else {
        p[0] = color.r; p[1] = color.g; p[2] = color.b;
    }
    p[3] = 0xFF;
}

void fill_rect(uint8_t *pixels, uint32_t width, uint32_t height, uint32_t pitch,
               int x, int y, int w, int h, int bgra, Color color) {
    for (int row = 0; row < h; row++)
        for (int col = 0; col < w; col++)
            put_pixel(pixels, width, height, pitch, x + col, y + row, bgra, color);
}

void draw_text(uint8_t *pixels, uint32_t width, uint32_t height, uint32_t pitch,
               int x, int y, const char *text, int scale, int bgra, Color color) {
    int cursor = x;
    for (const char *c = text; *c != '\0'; c++) {
        if (*c == '\0')
            break;
        const uint8_t *g = glyph(*c);
        for (int row = 0; row < 7; row++) {
            for (int col = 0; col < 5; col++) {
                if ((g[row] & (0x10u >> col)) == 0)
                    continue;
                fill_rect(pixels, width, height, pitch, cursor + col * scale, y + row * scale,
                          scale, scale, bgra, color);
            }
        }
        cursor += 6 * scale;
    }
}

}  // namespace

extern "C" {

void ps4_cheats_reset(void) {
    g_count = 0;
    memset(g_cheats, 0, sizeof(g_cheats));
}

void ps4_cheats_add(const char *name, const Ps4CheatWrite *writes, int count) {
    if (g_count >= kMaxCheats || name == nullptr || writes == nullptr || count <= 0 || count > kMaxWrites)
        return;
    Cheat &cheat = g_cheats[g_count++];
    cheat.name = name;
    cheat.count = count;
    for (int i = 0; i < count; i++)
        cheat.writes[i] = writes[i];
}

int ps4_cheats_count(void) {
    return g_count;
}

const char *ps4_cheats_name(int index) {
    return index >= 0 && index < g_count ? g_cheats[index].name : "";
}

int ps4_cheats_enabled(int index) {
    if (index < 0 || index >= g_count)
        return 0;
    char key[16];
    snprintf(key, sizeof(key), "cheat%d", index);
    return ps4_setting_get(key, 0) != 0;
}

void ps4_cheats_toggle(int index) {
    if (index < 0 || index >= g_count)
        return;
    const int on = ps4_cheats_enabled(index) ? 0 : 1;
    char key[16];
    snprintf(key, sizeof(key), "cheat%d", index);
    ps4_setting_set(key, on);
    printf("[cheats] %s: %s\n", g_cheats[index].name, on ? "on" : "off");
}

void ps4_cheats_apply(void) {
    if (!g_applied) {
        g_applied = true;
        ps4_cheats_init();
    }
    for (int i = 0; i < g_count; i++) {
        if (!ps4_cheats_enabled(i))
            continue;
        for (int j = 0; j < g_cheats[i].count; j++) {
            const Ps4CheatWrite &write = g_cheats[i].writes[j];
            uint8_t *address = guest_address(write.address);
            if (address != nullptr)
                store_be(address, write.value, write.width);
        }
    }
}

void ps4_cheat_menu_update(void) {
    const int requests = ps4_pad_take_quick_menu_requests();
    if (requests > 0) {
        const bool open = !g_menu_open.load(std::memory_order_acquire);
        g_menu_open.store(open, std::memory_order_release);
        if (open) {
            if (g_selected.load(std::memory_order_relaxed) >= ps4_cheats_count())
                g_selected.store(0, std::memory_order_relaxed);
            printf("[cheats] menu opened\n");
        }
    }

    const uint32_t now = ps4_pad_menu_buttons();
    if (!g_menu_open.load(std::memory_order_acquire)) {
        g_previous_buttons = now;
        return;
    }

    const uint32_t pressed = now & ~g_previous_buttons;
    g_previous_buttons = now;
    const int count = ps4_cheats_count();

    if (pressed & ORBIS_PAD_BUTTON_CIRCLE) {
        g_menu_open.store(false, std::memory_order_release);
        return;
    }
    if (count > 0) {
        int selected = g_selected.load(std::memory_order_relaxed);
        if (pressed & ORBIS_PAD_BUTTON_UP)
            selected = (selected + count - 1) % count;
        if (pressed & ORBIS_PAD_BUTTON_DOWN)
            selected = (selected + 1) % count;
        if (pressed & ORBIS_PAD_BUTTON_CROSS)
            ps4_cheats_toggle(selected);
        g_selected.store(selected, std::memory_order_relaxed);
    }
}

int ps4_cheat_menu_active(void) {
    return g_menu_open.load(std::memory_order_acquire) ? 1 : 0;
}

void ps4_cheat_menu_draw(uint8_t *pixels, uint32_t width, uint32_t height, uint32_t pitch, int bgra) {
    if (!g_menu_open.load(std::memory_order_acquire) || pixels == nullptr || pitch < width)
        return;

    const Color white{ 242, 242, 242 };
    const Color dim{ 180, 184, 196 };
    const Color cyan{ 23, 214, 232 };
    const Color gold{ 255, 204, 64 };
    const Color panel{ 10, 12, 20 };
    const Color border{ 70, 78, 104 };

    const int x = 64;
    const int y = 64;
    const int w = static_cast<int>(width) - 128;
    const int rows = ps4_cheats_count();
    int h = 220 + rows * 38;
    if (h > static_cast<int>(height) - 128)
        h = static_cast<int>(height) - 128;

    fill_rect(pixels, width, height, pitch, x, y, w, h, bgra, panel);
    for (int t = 0; t < 3; t++) {
        fill_rect(pixels, width, height, pitch, x + t, y + t, w - t * 2, 1, bgra, border);
        fill_rect(pixels, width, height, pitch, x + t, y + h - 1 - t, w - t * 2, 1, bgra, border);
        fill_rect(pixels, width, height, pitch, x + t, y + t, 1, h - t * 2, bgra, border);
        fill_rect(pixels, width, height, pitch, x + w - 1 - t, y + t, 1, h - t * 2, bgra, border);
    }
    draw_text(pixels, width, height, pitch, x + 32, y + 28, "CHEATS", 3, bgra, cyan);
    draw_text(pixels, width, height, pitch, x + 200, y + 30, "L3 + R3 CLOSE", 2, bgra, dim);
    fill_rect(pixels, width, height, pitch, x + 24, y + 76, w - 48, 2, bgra, border);

    if (rows == 0) {
        draw_text(pixels, width, height, pitch, x + 32, y + 120, "NO CHEATS AVAILABLE", 2, bgra, white);
    } else {
        const int selected = g_selected.load(std::memory_order_relaxed);
        for (int i = 0; i < rows; i++) {
            const int row_y = y + 104 + i * 38;
            if (row_y + 30 > y + h - 70)
                break;
            if (i == selected)
                fill_rect(pixels, width, height, pitch, x + 24, row_y - 4, w - 48, 34, bgra, Color{ 26, 42, 58 });
            char line[128];
            snprintf(line, sizeof(line), "%s %-28s %s", i == selected ? ">" : " ", ps4_cheats_name(i),
                     ps4_cheats_enabled(i) ? "ON" : "OFF");
            draw_text(pixels, width, height, pitch, x + 40, row_y, line, 2, bgra,
                      i == selected ? gold : (ps4_cheats_enabled(i) ? cyan : white));
        }
    }
    draw_text(pixels, width, height, pitch, x + 32, y + h - 48,
              "UP/DOWN SELECT   CROSS TOGGLE   CIRCLE CLOSE", 2, bgra, dim);
}

}  // extern "C"
