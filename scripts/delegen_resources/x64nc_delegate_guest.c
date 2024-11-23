#include <dlfcn.h>
#include <limits.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <x64nc/loaderapi.h>

#include "x64nc_shared.h"

#ifndef X64NC_API_FOREACH
#  define X64NC_API_FOREACH(X)
#endif

#define DynamicApis_LoadLibrary     x64nc_LoadLibrary
#define DynamicApis_GetProcAddress  x64nc_GetProcAddress
#define DynamicApis_FreeLibrary     x64nc_FreeLibrary
#define DynamicApis_GetErrorMessage x64nc_GetErrorMessage

#define DynamicApis_Name(NAME) ("my_" #NAME)
#define DynamicApis_Category   "Guest Delegate"

#ifdef __cplusplus
#  include <type_traits>
static constexpr auto _R(T &&value) {
    using NonConstType = std::remove_cv_t<std::remove_reference_t<T>>;
    return const_cast<NonConstType *>(&value);
}
#else
#  define _R(X) ((void *) &X)
#endif

// =================================================================================================
// Utils
static const char *DynamicApis_GetLibraryPath(const char *filename) {
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

static void DynamicApis_PostInitialize();
// =================================================================================================




// =================================================================================================
// Declare Function Pointers
#define _F(NAME) static __typeof__(&NAME) DynamicApis_p##NAME = NULL;
X64NC_API_FOREACH(_F)
#undef _F
// =================================================================================================




// =================================================================================================
// Constructor and Destructor
static void *DynamicApis_LibraryHandle = NULL;

void X64NC_CONSTRUCTOR DynamicApis_Constructor() {
    // 1. Load library
    void *dll = DynamicApis_LoadLibrary(
        (DynamicApis_GetLibraryPath(X64NC_HOST_DELEGATE_LIBRARY_NAME)), RTLD_NOW);
    if (!dll) {
        fprintf(stderr, DynamicApis_Category ": Load %s error: %s\n",
                X64NC_HOST_DELEGATE_LIBRARY_NAME, DynamicApis_GetErrorMessage());
        abort();
    }
    DynamicApis_LibraryHandle = dll;

    // 2. Get function addresses
#define _F(NAME)                                                                                   \
    {                                                                                              \
        DynamicApis_p##NAME = (__typeof__(DynamicApis_p##NAME)) (DynamicApis_GetProcAddress(       \
            dll, DynamicApis_Name(NAME)));                                                         \
        if (!DynamicApis_p##NAME) {                                                                \
            fprintf(stderr, DynamicApis_Category ": API %s cannot be resolved!\n", #NAME);         \
            abort();                                                                               \
        }                                                                                          \
    }
    X64NC_API_FOREACH(_F)
#undef _F
    DynamicApis_PostInitialize();
}

void X64NC_DESTRUCTOR DynamicApis_Destructor() {
    // Free library
    DynamicApis_FreeLibrary(DynamicApis_LibraryHandle);
}
// =================================================================================================




// =================================================================================================
// x64nc_delegate_guest_definitions.c
// 1. define all functions that forward the arguments and return value reference`
// 2. define all callback thunks
#include "_x64nc_delegate_guest_definitions.c"
// =================================================================================================




// =================================================================================================
// Utils
static void DynamicApis_PostInitialize() {
#define _F(SIGNATURE, FUNC) x64nc_RegisterCallThunk(SIGNATURE, (void *) FUNC);
    X64NC_CALLBACK_FOREACH(_F)
#undef _F
}
// =================================================================================================