#include <stddef.h>

#include "loaderapi.h"

#include "syscall_helper.h"
#include "x64nc_common.h"

void *x64nc_LoadLibrary(const char *path, int flags) {
    void *ret = NULL;
    void *a[] = {
        _reinterpret_cast(char *)(path),
        &flags,
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_LoadLibrary, a);
    return ret;
}

void x64nc_FreeLibrary(void *handle) {
    void *a[] = {
        handle,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_FreeLibrary, a);
}

void *x64nc_GetProcAddress(void *handle, const char *name) {
    void *ret = NULL;
    void *a[] = {
        handle,
        _const_cast(char *)(name),
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_GetProcAddress, a);
    return ret;
}

char *x64nc_GetErrorMessage() {
    char *ret = NULL;
    void *a[] = {
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_GetErrorMessage, a);
    return ret;
}

int x64nc_CallNativeProc(void *func, void *args[], void *ret) {
    typedef void (*Thunk)(void * /*callback*/, void * /*args*/, void * /*ret*/);

    void *a[] = {
        func,
        args,
        ret,
    };

    void *next_call[4];

    // Call and wait for the potential callback
    uint64_t syscall_ret = syscall3(X64NC_MAGIC_SYSCALL_INDEX,
                                    _reinterpret_cast(void *) X64NC_CallNativeProc, a, next_call);
    while (syscall_ret != X64NC_Result_Success) {
        switch (syscall_ret) {
            case X64NC_Result_Callback: {
                Thunk thunk = (Thunk) (next_call[0]);
                thunk(next_call[1], next_call[2], next_call[3]);

                // Notify host to continue and wait for the next callback
                syscall_ret = syscall1(X64NC_MAGIC_SYSCALL_INDEX,
                                       _reinterpret_cast(void *) X64NC_WaitForFinished);
                break;
            }

            case X64NC_Result_ThreadCreate: {
                break;
            }

            default:
                break;
        }
    }
    return 0;
}

void x64nc_RegisterCallThunk(const char *signature, void *func) {
    syscall3(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_RegisterCallThunk,
             _const_cast(char *)(signature), func);
}

void x64nc_ExtractVariadicList(const char *fmt, void **data_buf, char *types_buf) {
}

void x64nc_ExtractVariadicList_ScanF(const char *fmt, void **data_buf, char *types_buf) {
}