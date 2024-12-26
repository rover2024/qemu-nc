
#include "guestapi.h"

#include <stddef.h>
#include <stdio.h>

#include "syscall_helper.h"
#include "x64nc_common.h"

void *x64nc_LoadLibrary(const char *path, int flags) {
    void *ret = NULL;
    void *a[] = {
        (char *) (path),
        (void *) (uintptr_t) flags,
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_LoadLibrary, a);
    return ret;
}

int x64nc_FreeLibrary(void *handle) {
    int ret;
    void *a[] = {
        handle,
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_FreeLibrary, a);
    return ret;
}

void *x64nc_GetProcAddress(void *handle, const char *name) {
    void *ret = NULL;
    void *a[] = {
        handle,
        (char *) (name),
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_GetProcAddress, a);
    return ret;
}

char *x64nc_GetErrorMessage() {
    char *ret = NULL;
    void *a[] = {
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_GetErrorMessage, a);
    return ret;
}

char *x64nc_GetModulePath(void *addr, int is_handle){
    char *ret = NULL;
    void *a[] = {
        addr,
        (void *) (intptr_t) is_handle,
        ret, 
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_GetModulePath, a);
    return ret;
}

void x64nc_AddCallbackThunk(const char *signature, void *func) {
    void *a[] = {
        (char *) (signature),
        func,
    };
    syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_AddCallbackThunk, a);
}

char *x64nc_SearchLibrary(const char *path, int mode) {
    char *ret;
    void *a[] = {
        (char *) (path),
        (void *) (uintptr_t) mode,
        &ret,
    };
    syscall2(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_SearchLibrary, a);
    return ret;
}