#ifndef X64NC_HOSTAPI_H
#define X64NC_HOSTAPI_H

#include <x64nc/x64nc_global.h>

#ifdef __cplusplus
extern "C" {
#endif

X64NC_EXPORT void *x64nc_GetFPExecuteCallback();

X64NC_EXPORT void *x64nc_LookUpCallbackThunk(const char *sign);

X64NC_EXPORT void x64nc_HandleExtraGuestCall(int type, void *args[]);

X64NC_EXPORT void *x64nc_GetTranslatorApis();

X64NC_EXPORT char *x64nc_SearchLibraryH(const char *path, int mode);

#ifdef __cplusplus
}
#endif

#endif // X64NC_HOSTAPI_H
