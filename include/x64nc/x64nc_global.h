#ifndef X64NC_GLOBAL_H
#define X64NC_GLOBAL_H

#define X64NC_DECL_EXPORT __attribute__((visibility("default")))

#ifdef X64NC_LIBRARY
#  define X64NC_EXPORT X64NC_DECL_EXPORT
#else
#  define X64NC_EXPORT
#endif

#endif // X64NC_GLOBAL_H
