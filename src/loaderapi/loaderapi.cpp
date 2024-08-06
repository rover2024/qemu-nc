#include "loaderapi.h"

#include "syscall_helper.h"

void *x64nc_LoadLibrary(const char *path, int flags) {
    void *a[] = {
        (char *) (path),
        &flags,
    };
    return (void *) syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_LoadLibrary, a);
}

void x64nc_FreeLibrary(void *handle) {
    void *a[] = {
        handle,
    };
    syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_FreeLibrary, a);
}

void *x64nc_GetProcAddress(void *handle, const char *name) {
    void *a[] = {
        handle,
        const_cast<char *>(name),
    };
    return (void *) syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_GetProcAddress, a);
}

char *x64nc_GetErrorMessage() {
    return (char *) syscall1(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_GetErrorMessage);
}

int x64nc_CallNativeProc(void *func, void *args, void *ret) {
    using Callback = void (*)(void *args, void *ret);

    void *a[] = {
        func,
        args,
        ret,
    };

    void **cb;

    // Call and wait for the potential callback
    auto has_cb = syscall3(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_CallNativeProc, a, cb);
    while (has_cb) {
        auto func = reinterpret_cast<Callback>(cb[0]);
        func(cb[1], cb[2]);

        // Notify host to continue and wait for the next callback
        has_cb = syscall1(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_CallbackFinished);
    }
    return 0;
}

void x64nc_RegisterThunk(const char *signature, void *func) {
    syscall3(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_CallNativeProc,
             const_cast<char *>(signature), func);
}