# PS4: Mario Party 3: Recompiled's host as a PS4 app, included at the end of the upstream
# CMakeLists.txt when building with the port's toolchain (toolchain/ps4-mp3.cmake, and
# ps4-love-style.cmake as the project include: PS4_RUNTIME_SOURCES, ps4_link_mesa, ps4_add_eboot).

target_sources(MarioParty3Recompiled PRIVATE
    ${MP3_PS4_DIR}/ps4_log.cpp
    ${MP3_PS4_DIR}/ps4_platform.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../port/ps4_save_states.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../port/ps4_malloc_interpose.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../port/ps4_tls_stubs.cpp
    ${MP3_PS4_DIR}/ps4_pad.cpp
    ${MP3_PS4_DIR}/ps4_perf.cpp
    ${MP3_PS4_DIR}/ps4_quick_menu.cpp
    ${MP3_PS4_DIR}/ps4_wsi.cpp
    ${PS4_RUNTIME_SOURCES})
target_include_directories(MarioParty3Recompiled PRIVATE
    ${MP3_PS4_DIR}
    ${CMAKE_SOURCE_DIR}/lib/rt64/src/contrib/plume/contrib/Vulkan-Headers/include)
# The game target is built -fPIE (initial-exec) while the libraries are -fPIC (global-dynamic): the
# two emit different TLS reference stubs, and the initial-exec side's weak _ZTH" init references are
# unsatisfiable from the global-dynamic side. Match the libraries' model.
target_compile_options(MarioParty3Recompiled PRIVATE -ftls-model=global-dynamic)

# The runtime's game memory and the recompiled code's pages, through ps4_platform.cpp
target_include_directories(librecomp PRIVATE ${MP3_PS4_DIR})
target_include_directories(recompui PRIVATE ${MP3_PS4_DIR})
# Thread priorities and the performance log's stages (ps4_platform.h) in the runtime and RT64
target_include_directories(ultramodern PRIVATE ${MP3_PS4_DIR})
target_include_directories(rt64 PRIVATE ${MP3_PS4_DIR})

# The network library's shares (port/ps4_netfs.cpp: SMB and NFS under /net)
target_link_libraries(MarioParty3Recompiled PRIVATE ${PS4_SYSROOT}/lib/libnfs.a ${PS4_SYSROOT}/lib/libsmb2.a)
# Mesa's util (the whole-archive RADV below) uses zlib for the pipeline cache; built for the PS4
target_link_libraries(MarioParty3Recompiled PRIVATE ${PS4_SYSROOT}/lib/libz.a)
# every undefined symbol at once
target_link_options(MarioParty3Recompiled PRIVATE --error-limit=0)

# --wrap flags for pthread/clock/getaddrinfo (from ps4-love-style.cmake, applied per-target)
target_link_options(MarioParty3Recompiled PRIVATE
    --wrap=pthread_once --wrap=mmap --wrap=clock_gettime --wrap=pthread_create --wrap=getaddrinfo)

# RADV on GNM, the system libraries, and eboot.bin
ps4_link_mesa(MarioParty3Recompiled)
target_link_libraries(MarioParty3Recompiled PRIVATE
    SceSysmodule SceSystemService SceUserService SceVideoOut SceAudioOut ScePad SceNet)
ps4_add_eboot(MarioParty3Recompiled)

# zstd's dictionary builder sorts with qsort_r when _GNU_SOURCE is defined (the toolchain defines
# it); the PS4's C library has no qsort_r: its C90 fallback then.
set_source_files_properties("${CMAKE_SOURCE_DIR}/lib/rt64/src/contrib/zstd/lib/dictBuilder/cover.c"
    DIRECTORY "${CMAKE_SOURCE_DIR}/lib/rt64/src/contrib/zstd/build/cmake/lib"
    PROPERTIES COMPILE_OPTIONS "-U_GNU_SOURCE")

# re-spirv's command-line tool isn't needed on the console (its library is RT64's).
if (TARGET re-spirv-cli)
    set_target_properties(re-spirv-cli PROPERTIES EXCLUDE_FROM_ALL TRUE)
endif()

# SDL2's static target asks for -pthread and libm, which ld.lld (called directly) rejects: both are
# in the system libraries already.
if (TARGET SDL2::SDL2-static)
    set_target_properties(SDL2::SDL2-static PROPERTIES INTERFACE_LINK_LIBRARIES "")
endif()

# zstd's tracing hooks are weak symbols left undefined, which create-fself rejects ("missing module").
target_compile_definitions(libzstd_static PRIVATE ZSTD_TRACE=0)

# file_to_c is a host tool, not a PS4 executable: exclude from all and use pre-built binary
if (TARGET file_to_c AND NOT CMAKE_CROSSCOMPILING)
    set_target_properties(file_to_c PROPERTIES EXCLUDE_FROM_ALL TRUE)
endif()

# The C library's lstat calls its own fstatat, which --wrap=fstatat (port/ps4_fileat.cpp) leaves to
# __real_fstatat, and lld doesn't extract an archive member for that: pull it in by name, or
# create-fself finds "no module" for fstatat.
target_link_options(MarioParty3Recompiled PRIVATE --undefined=fstatat)
