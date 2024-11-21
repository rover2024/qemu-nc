#include "x64nc_declarations.h"

#ifndef X64NC_LIBRARY_NAME
#  define X64NC_LIBRARY_NAME "sample"
#endif

#define X64NC_HOST_DELEGATE_LIBRARY_NAME "lib" X64NC_LIBRARY_NAME "_host_bridge.so"
#define X64NC_HOST_LIBRARY_NAME          "lib" X64NC_LIBRARY_NAME ".so"