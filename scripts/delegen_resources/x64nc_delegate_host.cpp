#include <dlfcn.h>
#include <limits.h>

#include <cstdio>
#include <cstdlib>
#include <cstring>

#include <x64nc/call_helper.h>
#include <x64nc/x64nc_global.h>

#include "x64nc_shared.h"

// API Implementions
namespace {

    static const char *get_library_path(const char *filename) {
        char *dir = getenv("X64NC_HOST_LIBRARY_DIR");
        if (!dir) {
            fprintf(stderr, "Error: unable to get library path.\n");
            abort();
        }

        static char result[PATH_MAX];
        strcpy(result, dir);
        strcpy(result + strlen(dir), filename);
        return result;
    }

    namespace DynamicApis {

// Declare Function Pointers
#define _F(NAME) decltype(&::NAME) p##NAME = nullptr;
        X64NC_API_FOREACH_FUNCTION(_F)
#undef _F

        struct initializer {

            initializer() {
                // Load Library
                auto dll = dlopen(get_library_path(X64NC_HOST_LIBRARY_NAME), RTLD_NOW);
                if (!dll) {
                    printf("Host Delegate: Load %s error: %s\n", X64NC_HOST_LIBRARY_NAME,
                           dlerror());
                    abort();
                }

                _hDll = dll;

// Get Function Addresses
#define _F(NAME)                                                                                   \
    {                                                                                              \
        p##NAME = reinterpret_cast<decltype(p##NAME)>(dlsym(dll, #NAME));                          \
        if (!p##NAME) {                                                                            \
            printf("Host Delegate: API %s cannot be resolved!\n", #NAME);                          \
            abort();                                                                               \
        }                                                                                          \
    }
                X64NC_API_FOREACH_FUNCTION(_F)
#undef _F
            }

            ~initializer() {
                // Kernel with remove at end
                dlclose(_hDll);
            }

            void *_hDll;

        } dummy;

    }
}

#include "x64nc_delegate_host_definitions.cpp"