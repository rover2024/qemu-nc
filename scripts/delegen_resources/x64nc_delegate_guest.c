#define _GNU_SOURCE

#include <dlfcn.h>
#include <limits.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define X64NC_GUEST_DELEGATE_SOURCE

#ifdef __cplusplus
#  include <type_traits>
static constexpr auto _R(T &&value) {
    using NonConstType = std::remove_cv_t<std::remove_reference_t<T>>;
    return const_cast<NonConstType *>(&value);
}
#else
#  define _R(X) ((void *) &X)
#endif

#include <x64nc/guestapi.h>
#include <x64nc/x64nc_common.h>

#include "x64nc_shared.h"

#ifndef X64NC_API_FOREACH
#  define X64NC_API_FOREACH(X)
#endif

#define DynamicApis_SearchLibrary(NAME) x64nc_SearchLibrary(NAME, X64NC_SL_Mode_G2D)
#define DynamicApis_LoadLibrary         x64nc_LoadLibrary
#define DynamicApis_GetProcAddress      x64nc_GetProcAddress
#define DynamicApis_FreeLibrary         x64nc_FreeLibrary
#define DynamicApis_GetErrorMessage     x64nc_GetErrorMessage

#define DynamicApis_Name(NAME) ("my_" #NAME)
#define DynamicApis_Category   "Guest Delegate"

// =================================================================================================
// Utils
static const char *GetThisLibraryName() {
    Dl_info info;
    dladdr(GetThisLibraryName, &info);
    return strrchr(info.dli_fname, '/') + 1;
}

static void DynamicApis_PreInitialize();

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

static void X64NC_CONSTRUCTOR DynamicApis_Constructor() {
    DynamicApis_PreInitialize();

    // 1. Load library
    const char *path = DynamicApis_SearchLibrary(GetThisLibraryName());
    if (!path) {
        printf(DynamicApis_Category ": Search %s failed\n", X64NC_LIBRARY_NAME);
        abort();
    }
    printf("LOAD %s\n", path);
    void *dll = DynamicApis_LoadLibrary(path, RTLD_NOW);
    if (!dll) {
        printf(DynamicApis_Category ": Load %s error: %s\n", path, DynamicApis_GetErrorMessage());
        abort();
    }
    DynamicApis_LibraryHandle = dll;

    // 2. Get function addresses
#define _F(NAME)                                                                                                       \
    {                                                                                                                  \
        DynamicApis_p##NAME =                                                                                          \
            (__typeof__(DynamicApis_p##NAME)) (DynamicApis_GetProcAddress(dll, DynamicApis_Name(NAME)));               \
        if (!DynamicApis_p##NAME) {                                                                                    \
            printf(DynamicApis_Category ": API %s cannot be resolved!\n", #NAME);                                      \
            abort();                                                                                                   \
        }                                                                                                              \
    }
    X64NC_API_FOREACH(_F)
#undef _F

    DynamicApis_PostInitialize();
}

static void X64NC_DESTRUCTOR DynamicApis_Destructor() {
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
static void DynamicApis_PreInitialize() {
#define _F(SIGNATURE, FUNC) x64nc_AddCallbackThunk(SIGNATURE, (void *) FUNC);
    X64NC_CALLBACK_FOREACH(_F)
#undef _F
}

static void DynamicApis_PostInitialize() {
}
// =================================================================================================