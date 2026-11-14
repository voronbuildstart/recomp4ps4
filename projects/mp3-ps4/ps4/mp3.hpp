// Mario Party 3: Recompiled for PS4 - game-facing support header for the port's own code.
//
// The quick menu (ps4_quick_menu.cpp) and the perf/crash paths talk to the game through here.

#pragma once

#include <filesystem>
#include <mutex>
#include <string>
#include <vector>

namespace mp3 {

// Save states (frontend.cpp seeds the keys + the runtime's idle moment that states are taken at).
namespace save_states {
    void init();
    void save();
    void load();
    int next_slot();
    int slot();
    void set_slot(int slot);
    int slot_count_total();
    std::filesystem::path slot_file(int slot);
}

// Graphics config: the settings window's own flag.
bool graphics_config_ready();

} // namespace mp3
