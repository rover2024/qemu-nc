#include "guestapi.h"

#define _GNU_SOURCE

#include <dlfcn.h>
#include <limits.h>

#include <stddef.h>
#include <stdlib.h>

#include "x64nc_common.h"

// #undef x64nc_debug
// #define x64nc_debug printf

void *x64nc_GetProcAddress_N2G(void *addr, int is_handle, const char *name) {
    x64nc_debug("GRT: invoked %s, addr=%p, is_handle=%d, name=%s\n", __func__, addr, is_handle, name);
    void *test_handle = dlsym(RTLD_DEFAULT, name);
    if (test_handle) {
        x64nc_debug("GRT: test handle found %p\n", test_handle);
        return test_handle;
    }
    const char *host_library_path = x64nc_GetModulePath(addr, is_handle);
    if (!host_library_path) {
        x64nc_debug("GRT: host library not found\n");
        return NULL;
    }
    x64nc_debug("GRT: host library: %s\n", host_library_path);
    static char staticRealPath[PATH_MAX];
    host_library_path = realpath(host_library_path, staticRealPath);

    const char *guest_library_path = x64nc_SearchLibrary(host_library_path, X64NC_SL_Mode_N2G);
    if (!guest_library_path) {
        x64nc_debug("GRT: guest library not found\n");
        return NULL;
    }
    x64nc_debug("GRT: guest library: %s\n", guest_library_path);

    void *guest_handle = dlopen(guest_library_path, RTLD_NOW | RTLD_NOLOAD);
    if (!guest_handle) {
        guest_handle = dlopen(guest_library_path, RTLD_NOW);
        if (!guest_handle) {
            x64nc_debug("GRT: guest library cannot be opened\n");
            return NULL;
        }
    }
    return dlsym(guest_handle, name);
}