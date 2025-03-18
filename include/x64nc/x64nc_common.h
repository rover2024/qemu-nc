#ifndef X64NC_COMMON_H
#define X64NC_COMMON_H

#include <stdio.h>

#define X64NC_MAGIC_SYSCALL_INDEX 114514

enum X64NC_MAGIC_SYSCALL_TYPE {
    X64NC_CheckHealth = 0,

    // Loader, implemented in QEMU
    X64NC_LoadLibrary,
    X64NC_FreeLibrary,
    X64NC_GetProcAddress,
    X64NC_GetErrorMessage,
    X64NC_GetModulePath,

    // Loader Metadata, implemented in HostRuntime
    X64NC_AddCallbackThunk,
    X64NC_SearchLibrary,

    // Native Proc, implemented in QEMU
    X64NC_CallNativeProc,
    X64NC_ResumeNativeProc,

    // Symbol Audit, implemented in HostRuntime
    X64NC_LA_ObjOpen,
    X64NC_LA_ObjClose,
    X64NC_LA_PreInit,
    X64NC_LA_SymBind,
};

enum X64NC_NATIVE_PROC_RESULT {
    X64NC_NP_Result_Finished = 0,
    X64NC_NP_Result_Callback,
    X64NC_NP_Result_PThreadCreate,
    X64NC_NP_Result_PThreadExit,
};

enum X64NC_NATIVE_PROC_CONVENTION {
    X64NC_NP_Convention_Normal,
    X64NC_NP_Convention_ThreadEntry,
};

enum X64NC_SEARCH_LIBRARY_MODE {
    X64NC_SL_Mode_G2H, // guest delegate -> host delegate
    X64NC_SL_Mode_G2N, // host delegate  -> native
    X64NC_SL_Mode_H2G,
    X64NC_SL_Mode_H2N,
    X64NC_SL_Mode_N2G,
    X64NC_SL_Mode_N2H,
};

#if 0
#  define x64nc_debug printf
#else
#  define x64nc_debug
#endif

enum X64NC_VARIADIC_PROTOCOL {
    X64NC_VP_SCANF,
    X64NC_VP_PRINTF,
};

enum X64NC_VARIADIC_ARGUMENT_TYPE {
    X64NC_VA_CHAR = 1,
    X64NC_VA_SHORT,
    X64NC_VA_LONG,
    X64NC_VA_LONGLONG,
    X64NC_VA_FLOAT,
    X64NC_VA_DOUBLE,
    X64NC_VA_POINTER,
};

struct X64NC_VArgEntry {
    int type;

    union {
        char c;
        short s;
        int i;
        long l;
        long long ll;
        float f;
        double d;
        void *p;
    };
};

#endif // X64NC_COMMON_H
