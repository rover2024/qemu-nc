#ifndef X64NC_COMMON_H
#define X64NC_COMMON_H

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
    X64NC_SL_Mode_G2D, // guest -> delegate
    X64NC_SL_Mode_G2H, // guest -> host
    X64NC_SL_Mode_D2G,
    X64NC_SL_Mode_D2H,
    X64NC_SL_Mode_H2G,
    X64NC_SL_Mode_H2D,
};

#endif // X64NC_COMMON_H
