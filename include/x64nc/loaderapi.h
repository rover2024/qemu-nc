#ifndef X64NC_LOADERAPI_H
#define X64NC_LOADERAPI_H

#include <stdarg.h>

#include <x64nc/x64nc_global.h>

#ifdef __cplusplus
extern "C" {
#endif

X64NC_EXPORT void *x64nc_LoadLibrary(const char *path, int flags);

X64NC_EXPORT int x64nc_FreeLibrary(void *handle);

X64NC_EXPORT void *x64nc_GetProcAddress(void *handle, const char *name);

X64NC_EXPORT char *x64nc_GetErrorMessage();

X64NC_EXPORT int x64nc_CallNativeProc(void *func, void *args[], void *ret);

X64NC_EXPORT void x64nc_RegisterCallThunk(const char *signature, void *func);

X64NC_EXPORT void x64nc_ExtractVariadicList(const char *fmt, void **data_buf, char *types_buf);

X64NC_EXPORT void x64nc_ExtractVariadicList_ScanF(const char *fmt, void **data_buf, char *types_buf);

#ifdef __cplusplus
}
#endif

#endif // X64NC_LOADERAPI_H
