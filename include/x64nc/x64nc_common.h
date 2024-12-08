#ifndef X64NC_COMMON_H
#define X64NC_COMMON_H

#define X64NC_MAGIC_SYSCALL_INDEX 114514

enum X64NC_MAGIC_SYSCALL_TYPE {
    X64NC_CheckHealth = 0,

    X64NC_LoadLibrary = 0x1,
    X64NC_FreeLibrary,
    X64NC_GetProcAddress,
    X64NC_GetErrorMessage,
    X64NC_CallNativeProc,
    X64NC_WaitForFinished,

    X64NC_LA_ObjOpen,
    X64NC_LA_ObjClose,
    X64NC_LA_PreInit,
    X64NC_LA_SymBind,

    X64NC_RegisterCallThunk,
};

enum X64NC_MAGIC_SYSCALL_RESULT {
    X64NC_Result_Success = 0,
    X64NC_Result_Callback,
    X64NC_Result_ThreadCreate,
    X64NC_Result_ThreadExit,
};

enum X64NC_THUNK_ID {
    X64NC_Thunk_HostExecuteCallback = 1,
    X64NC_Thunk_HostExtraEvent,
    X64NC_Thunk_GetHostLastThreadId,
    X64NC_Thunk_ThreadCreate,
    X64NC_Thunk_ThreadExit,
};

#ifdef __cplusplus
#  define _const_cast(T)       const_cast<T>
#  define _reinterpret_cast(T) reinterpret_cast<T>
#else
#  define _const_cast(T)       (T)
#  define _reinterpret_cast(T) (T)
#endif

#endif // X64NC_COMMON_H
