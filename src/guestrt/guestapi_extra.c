#include "guestapi.h"

#include <dlfcn.h>

#include <stddef.h>

void *x64nc_GetProcAddress_H2G(void *addr, int is_handle, const char *name) {
    const char *host_library_path = x64nc_GetModulePath(addr, is_handle);
    if (!host_library_path) {
        return NULL;
    }
    const char *guest_library_path = x64nc_SearchLibrary(host_library_path, 0);
    if (!guest_library_path) {
        return NULL;
    }

    void *guest_handle = dlopen(host_library_path, RTLD_NOW | RTLD_NOLOAD);
    if (!guest_handle) {
        guest_handle = dlopen(host_library_path, RTLD_NOW);
        if (!guest_handle) {
            return NULL;
        }
    }
    return dlsym(guest_handle, name);
}