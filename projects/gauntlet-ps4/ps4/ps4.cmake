# PS4: Gauntlet Legends: Recompiled's host as a PS4 app, included at the end of CMakeLists.txt
# when building with the port's toolchain (toolchain/ps4-gauntlet.cmake, and ps4-love-style.cmake as
# the project include: PS4_RUNTIME_SOURCES, ps4_link_mesa, ps4_add_eboot).

target_sources(GauntletRecompiled PRIVATE
    ${GAUNTLET_PS4_DIR}/ps4_log.cpp
    ${GAUNTLET_PS4_DIR}/ps4_platform.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../port/ps4_malloc_interpose.cpp
    ${GAUNTLET_PS4_DIR}/ps4_pad.cpp
    ${GAUNTLET_PS4_DIR}/ps4_perf.cpp
    ${GAUNTLET_PS4_DIR}/ps4_quick_menu.cpp
    ${GAUNTLET_PS4_DIR}/ps4_cheats_game.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../../_ps4-common/ps4_cheats.cpp
    ${GAUNTLET_PS4_DIR}/ps4_wsi.cpp
    ${PS4_RUNTIME_SOURCES})
target_include_directories(GauntletRecompiled PRIVATE
    ${GAUNTLET_PS4_DIR}
    ${CMAKE_CURRENT_LIST_DIR}/../../_ps4-common
    "${RT64_DIR}/src/contrib/Vulkan-Headers/include")

# The runtime's game memory and the recompiled code's pages, through ps4_platform.cpp
target_include_directories(librecomp PRIVATE ${GAUNTLET_PS4_DIR})
target_include_directories(ultramodern PRIVATE ${GAUNTLET_PS4_DIR})
# Thread priorities and the performance log's stages (ps4_platform.h) in the runtime and RT64
target_include_directories(rt64 PRIVATE ${GAUNTLET_PS4_DIR})

# The network library's shares (port/ps4_netfs.cpp: SMB and NFS under /net)
target_link_libraries(GauntletRecompiled PRIVATE ${PS4_SYSROOT}/lib/libnfs.a ${PS4_SYSROOT}/lib/libsmb2.a)
# Mesa's util (whole-archive) hash/compress pull zlib's crc32/deflate/inflate through; link the
# port's sysroot's static libz.
target_link_libraries(GauntletRecompiled PRIVATE ${PS4_SYSROOT}/lib/libz.a)
# every undefined symbol at once
target_link_options(GauntletRecompiled PRIVATE --error-limit=0)

# --wrap flags for pthread/clock/getaddrinfo (from ps4-love-style.cmake, applied per-target)
target_link_options(GauntletRecompiled PRIVATE
    --wrap=pthread_once --wrap=mmap --wrap=clock_gettime --wrap=pthread_create --wrap=getaddrinfo)

# RADV on GNM, the system libraries, and eboot.bin
ps4_link_mesa(GauntletRecompiled)
target_link_libraries(GauntletRecompiled PRIVATE
    SceSysmodule SceSystemService SceUserService SceVideoOut SceAudioOut ScePad SceNet)
ps4_add_eboot(GauntletRecompiled)

# zstd's dictionary builder sorts with qsort_r when _GNU_SOURCE is defined (the toolchain defines
# it); the PS4's C library has no qsort_r: its C90 fallback then.
set_source_files_properties("${RT64_DIR}/src/contrib/zstd/lib/dictBuilder/cover.c"
    DIRECTORY "${RT64_DIR}/src/contrib/zstd/build/cmake/lib"
    PROPERTIES COMPILE_OPTIONS "-U_GNU_SOURCE")

# re-spirv's command-line tool isn't needed on the console (its library is RT64's).
if (TARGET re-spirv-cli)
    set_target_properties(re-spirv-cli PROPERTIES EXCLUDE_FROM_ALL TRUE)
endif()
# The texture tools are host tools, not part of the console app; with the malloc-replace CRT
# (every executable links with it) they can't link at all, so keep them out of the default build.
if (TARGET texture_hasher)
    set_target_properties(texture_hasher PROPERTIES EXCLUDE_FROM_ALL TRUE)
endif()
if (TARGET texture_packer)
    set_target_properties(texture_packer PROPERTIES EXCLUDE_FROM_ALL TRUE)
endif()

# SDL2's static target asks for -pthread and libm, which ld.lld (called directly) rejects: both are
# in the system libraries already.
if (TARGET SDL2::SDL2-static)
    set_target_properties(SDL2::SDL2-static PROPERTIES INTERFACE_LINK_LIBRARIES "")
endif()

# zstd's tracing hooks are weak symbols left undefined, which create-fself rejects ("missing module").
target_compile_definitions(libzstd_static PRIVATE ZSTD_TRACE=0)

# file_to_c is a host tool, not a PS4 executable: exclude from all and use pre-built binary
if (TARGET file_to_c)
    set_target_properties(file_to_c PROPERTIES EXCLUDE_FROM_ALL TRUE)
endif()

# The C library's lstat calls its own fstatat, which --wrap=fstatat (port/ps4_fileat.cpp) leaves to
# __real_fstatat, and lld doesn't extract an archive member for that: pull it in by name, or
# create-fself finds "no module" for fstatat.
target_link_options(GauntletRecompiled PRIVATE --undefined=fstatat)
