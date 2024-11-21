#ifndef X64NC_HOSTAPI_H
#define X64NC_HOSTAPI_H

#include <x64nc/x64nc_global.h>

#ifdef __cplusplus
extern "C" {
#endif

// Host Api
X64NC_EXPORT void QEMU_NC_CallHostExecuteCallback(void *thunk, void *callback, void *args,
                                                  void *ret);

X64NC_EXPORT void *QEMU_NC_GetHostExecuteCallback();

X64NC_EXPORT void *QEMU_NC_LookUpGuestThunk(const char *sign);

#ifdef __cplusplus
}
#endif

#endif // X64NC_HOSTAPI_H
