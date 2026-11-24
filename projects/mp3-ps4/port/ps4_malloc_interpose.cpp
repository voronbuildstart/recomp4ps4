// Every malloc of the process — libc-internal and ours — goes to our dlmalloc heap instead of
// the system libc's: its lazy reservation of 2.5 GiB of system flexible memory at the first
// malloc fails on this console (kernel returns an error, the libc calls sceLibcMspaceMalloc with
// a NULL mspace, and the process dies inside it). The static initializers alone allocate during
// static init (recompui's launcher tables), before main() exists.
//
// Strong symbols, linked before -lc on the command line, so libc.a's malloc/free/calloc/realloc
// members are never pulled in and every reference — ours and the libc's — lands here.
//
// The dlmalloc side itself (getHeap/createHeap, per-thread arenas) is port/ps4_runtime.cpp.

#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>  // SIZE_MAX

namespace {
extern "C" void* __wrap_malloc(size_t);
extern "C" void __wrap_free(void*);
extern "C" void* __wrap_calloc(size_t, size_t);
extern "C" void* __wrap_realloc(void*, size_t);
extern "C" void* __wrap_memalign(size_t, size_t);
size_t page_size() { static size_t size = 0; if (!size) { size = 16384; } return size; }
} // namespace

extern "C" void* malloc(size_t size) { return __wrap_malloc(size); }
extern "C" void free(void* ptr) { __wrap_free(ptr); }
extern "C" void* calloc(size_t nelem, size_t size) { return __wrap_calloc(nelem, size); }
extern "C" void* realloc(void* ptr, size_t size) { return __wrap_realloc(ptr, size); }
extern "C" void* memalign(size_t alignment, size_t size) { return __wrap_memalign(alignment, size); }
extern "C" void* aligned_alloc(size_t alignment, size_t size) { return __wrap_memalign(alignment, size); }
extern "C" void* valloc(size_t size) { return __wrap_memalign(page_size(), size); }
extern "C" void* pvalloc(size_t size) {
    const size_t page = page_size();
    return __wrap_memalign(page, (size + page - 1) & ~(page - 1));
}
// Checked multiply, then realloc.
extern "C" void* reallocarray(void* ptr, size_t nmemb, size_t size) {
    if (size != 0 && nmemb > SIZE_MAX / size) {
        errno = ENOMEM;
        return nullptr;
    }
    return __wrap_realloc(ptr, nmemb * size);
}
extern "C" int posix_memalign(void** out, size_t alignment, size_t size) {
    if (!out || alignment < 2 * sizeof(void*) || (alignment & (alignment - 1)) != 0)
        return EINVAL;
    void* p = __wrap_memalign(alignment, size);
    if (!p)
        return ENOMEM;
    *out = p;
    return 0;
}
// The size free will hand back; SDL and partners probe for it.
extern "C" size_t malloc_usable_size(void* ptr) {
    extern size_t mspace_usable_size(const void*);
    if (!ptr)
        return 0;
    // The chunk headers are dlmalloc FOOTERS: the size of the allocation follows the object for
    // mspace_usable_size either way (dlmalloc looks at the header for chunks).
    return mspace_usable_size(ptr);
}
// Some code uses the obsolete name.
extern "C" void cfree(void* ptr) { free(ptr); }
