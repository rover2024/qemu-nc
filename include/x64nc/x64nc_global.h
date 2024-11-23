#ifndef X64NC_GLOBAL_H
#define X64NC_GLOBAL_H

#define X64NC_DECL_EXPORT __attribute__((visibility("default")))
#define X64NC_CONSTRUCTOR __attribute__((constructor))
#define X64NC_DESTRUCTOR  __attribute__((destructor))

#ifdef X64NC_LIBRARY
#  define X64NC_EXPORT X64NC_DECL_EXPORT
#else
#  define X64NC_EXPORT
#endif

#ifdef __cplusplus
#  define X64NC_EXTERN_C       extern "C"
#  define X64NC_EXTERN_C_BEGIN extern "C" {
#  define X64NC_EXTERN_C_END   }
#else
#  define X64NC_EXTERN_C
#  define X64NC_EXTERN_C_BEGIN
#  define X64NC_EXTERN_C_END
#endif

#endif // X64NC_GLOBAL_H
