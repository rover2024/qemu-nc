#ifndef HOSTAPI_H
#define HOSTAPI_H

#include <x64nc/x64nc_global.h>

#ifdef __cplusplus
extern "C" {
#endif

// Host Api
X64NC_EXPORT void CallHostExecuteCallback(void *callback, void *args, void *ret);

X64NC_EXPORT void *GetHostExecuteCallback();

X64NC_EXPORT void *LookUpGuestThunk(const char *sign);

#ifdef __cplusplus
}
#endif

#endif // HOSTAPI_H
