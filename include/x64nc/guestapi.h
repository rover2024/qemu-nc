#ifndef X64NC_GUESTAPI_H
#define X64NC_GUESTAPI_H

#include <x64nc/x64nc_global.h>

#ifdef __cplusplus
extern "C" {
#endif

// Base
X64NC_EXPORT void *x64nc_LoadLibrary(const char *path, int flags);

X64NC_EXPORT int   x64nc_FreeLibrary(void *handle);

X64NC_EXPORT void *x64nc_GetProcAddress(void *handle, const char *name);

X64NC_EXPORT char *x64nc_GetErrorMessage();

X64NC_EXPORT char *x64nc_GetModulePath(void *addr, int is_handle);

X64NC_EXPORT void  x64nc_AddCallbackThunk(const char *sign, void *func);

X64NC_EXPORT char *x64nc_SearchLibrary(const char *path, int mode);

X64NC_EXPORT void  x64nc_CallNativeProc(void *func, void *args[], void *ret, int convention);

// Extra
X64NC_EXPORT void *x64nc_GetProcAddress_H2G(void *addr, int is_handle, const char *name);

#ifdef __cplusplus
}
#endif

#endif // X64NC_GUESTAPI_H