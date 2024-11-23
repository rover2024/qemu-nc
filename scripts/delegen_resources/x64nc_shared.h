
#include <x64nc/x64nc_global.h>

// =================================================================================================
// x64nc_declarations.h
// 1. include all needed headers of the library in correct order
// 2. define X64NC_API_FOREACH
// 3. define X64NC_CALLBACK_FOREACH

#include "_x64nc_declarations.h"
// =================================================================================================

#ifndef X64NC_LIBRARY_NAME
#  define X64NC_LIBRARY_NAME "sample"
#endif

#define X64NC_HOST_DELEGATE_LIBRARY_NAME "lib" X64NC_LIBRARY_NAME "_host_bridge.so"
#define X64NC_HOST_LIBRARY_NAME          "lib" X64NC_LIBRARY_NAME ".so"