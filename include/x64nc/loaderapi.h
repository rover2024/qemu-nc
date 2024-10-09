#ifndef X64NC_x64nc_H
#define X64NC_x64nc_H

#include <x64nc/x64nc_global.h>

#ifdef __cplusplus
extern "C" {
#endif

X64NC_EXPORT void *x64nc_LoadLibrary(const char *path, int flags);

X64NC_EXPORT void x64nc_FreeLibrary(void *handle);

X64NC_EXPORT void *x64nc_GetProcAddress(void *handle, const char *name);

X64NC_EXPORT char *x64nc_GetErrorMessage();

X64NC_EXPORT int x64nc_CallNativeProc(void *func, void *args, void *ret);

X64NC_EXPORT void x64nc_RegisterCallThunk(const char *signature, void *func);

#ifdef __cplusplus
}
#endif

#endif // X64NC_x64nc_H
