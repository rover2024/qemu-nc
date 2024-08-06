#ifndef X64NC_x64nc_H
#define X64NC_x64nc_H

#include <x64nc/x64nc_global.h>

#ifdef __cplusplus
extern "C" {
#endif

const int X64NC_MAGIC_SYSCALL_INDEX = 114514;

enum X64NC_MAGIC_SYSCALL_TYPE {
    X64NC_LoadLibrary = 0x1,
    X64NC_FreeLibrary,
    X64NC_GetProcAddress,
    X64NC_GetErrorMessage,
    X64NC_CallNativeProc,
    X64NC_CallbackFinished,

    X64NC_UserCall = 0x1000,
};

X64NC_EXPORT void *x64nc_LoadLibrary(const char *path, int flags);

X64NC_EXPORT void x64nc_FreeLibrary(void *handle);

X64NC_EXPORT void *x64nc_GetProcAddress(void *handle, const char *name);

X64NC_EXPORT char *x64nc_GetErrorMessage();

X64NC_EXPORT int x64nc_CallNativeProc(void *func, void *args, void *ret);

X64NC_EXPORT void x64nc_RegisterThunk(const char *signature, void *func);

#ifdef __cplusplus
}
#endif

#endif // X64NC_x64nc_H
