// Harvest Moon 64: Recompiled for PS4: the game-facing support (hm64.hpp): the quick menu's save
// states and its graphics-config readiness check.
//
// The runtime has no emulator save states (nothing serializes the CPU). The PS4's slots are
// EEPROM save files: every save write lands in <config>/saves/<game id>.bin, flushed by the
// runtime's saving thread (librecomp/src/pi.cpp), so slot N is a copy of that file under
// <config>/saves/save_states/. save() copies it out, load() copies it back and makes the running
// game re-read it (ultramodern::change_save_file to the same path: the save buffer is refilled).

#include "hm64.hpp"

#include <filesystem>
#include <system_error>
#include <utility>

#include "ultramodern/ultramodern.hpp"
#include "librecomp/game.hpp"
#include "recompui/config.h"
#include "ps4_log.h"

namespace hm64 {

namespace save_states {

namespace {
std::mutex slot_mutex;
int current_slot = 1;  // 1-based
constexpr int slot_count = 9;

// The slots live beside the game's save file: <config>/saves/save_states/slot_N.bin
std::filesystem::path slot_path(int n) {
    std::filesystem::path base = ultramodern::get_save_file_path();
    if (base.empty()) {
        // Not initialized yet (before the game starts): fall back to the app's config path.
        base = recomp::get_config_path() / "saves" / "placeholder.bin";
    }
    return base.parent_path() / "save_states" / ("slot_" + std::to_string(n) + ".bin");
}

bool file_exists(const std::filesystem::path &path) {
    std::error_code ec;
    return std::filesystem::is_regular_file(path, ec);
}
} // namespace

void init() {} // The quick menu drives these directly; nothing to do here.

void save() {
    const int n = slot();
    const auto src = ultramodern::get_save_file_path();
    const auto dst = slot_path(n);
    std::error_code ec;
    std::filesystem::create_directories(dst.parent_path(), ec);
    if (src.empty() || !file_exists(src)) {
        LOG_WARN("save state: no game save file yet ({})", src.string());
        return;
    }
    std::filesystem::copy_file(src, dst, std::filesystem::copy_options::overwrite_existing, ec);
    if (ec) {
        LOG_ERROR("save state slot {}: couldn't copy {} to {}: {}", n, src.string(), dst.string(), ec.message());
        return;
    }
    LOG_INFO("save state slot {} saved ({})", n, src.string());
}

void load() {
    const int n = slot();
    const auto dst = ultramodern::get_save_file_path();
    const auto src = slot_path(n);
    std::error_code ec;
    if (dst.empty()) {
        LOG_WARN("load state: the game's save file path isn't set yet");
        return;
    }
    if (!file_exists(src)) {
        LOG_WARN("load state: slot {} is empty", n);
        return;
    }
    std::filesystem::create_directories(dst.parent_path(), ec);
    std::filesystem::copy_file(src, dst, std::filesystem::copy_options::overwrite_existing, ec);
    if (ec) {
        LOG_ERROR("load state slot {}: couldn't copy {} to {}: {}", n, src.string(), dst.string(), ec.message());
        return;
    }
    // Make the running game re-read the file just written (the buffer is refilled from disk).
    ultramodern::change_save_file(u8"", recomp::current_game_id());
    LOG_INFO("save state slot {} loaded", n);
}

int next_slot() {
    std::lock_guard lock(slot_mutex);
    current_slot = current_slot % slot_count + 1;
    return current_slot;
}

int slot() {
    std::lock_guard lock(slot_mutex);
    return current_slot;
}

void set_slot(int n) {
    if (n >= 1 && n <= slot_count) {
        std::lock_guard lock(slot_mutex);
        current_slot = n;
    }
}

int slot_count_total() {
    return slot_count;
}

std::filesystem::path slot_file(int n) {
    return slot_path(n);
}

} // namespace save_states

// The graphics config exists once recompui has built its tab (recompui throws until then).
bool graphics_config_ready() {
    try {
        static_cast<void>(recompui::config::get_graphics_config());
        return true;
    } catch (const std::runtime_error &) {
        return false;
    }
}

} // namespace hm64
