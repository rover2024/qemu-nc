#include <stddef.h>
#include <pthread.h>
#include <stdio.h>

#include "loaderapi.h"

#include "syscall_helper.h"
#include "x64nc_common.h"

struct thread_info {
    pthread_t thread;
    pthread_mutex_t mutex;
    pthread_cond_t cond;
    void *host_entry;
    void *host_args;
};

static void *pthread_create_entry(void *args) {
    struct thread_info *info = args;

    void *entry = info->host_entry;
    void *arg = info->host_args;

    /* Signal to the parent that we're ready.  */
    pthread_mutex_lock(&info->mutex);
    pthread_cond_broadcast(&info->cond);
    pthread_mutex_unlock(&info->mutex);
    /* Wait until the parent has finished initializing the tls state.  */

    printf("pthread_create_entry: %p %p\n", entry, arg);
    fflush(stdout);
    void *ret;
    x64nc_CallNativeProcEx(entry, arg, &ret, 1);
    return ret;
}

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

int x64nc_FreeLibrary(void *handle) {
    int ret;
    void *a[] = {
        handle,
        &ret,
    };
    (void) syscall2(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_FreeLibrary, a);
    return ret;
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

int x64nc_CallNativeProcEx(void *func, void *args[], void *ret, int convention) {
    typedef void (*Thunk)(void * /*callback*/, void * /*args*/, void * /*ret*/);

    void *a[] = {
        func,
        args,
        ret,
        (void *) (intptr_t) convention,
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
                break;
            }

            case X64NC_Result_ThreadCreate: {
                void **event_args = next_call[0];
                void **pthread_create_args = (void **) event_args[0];
                int *pthread_create_ret = event_args[1];

                struct thread_info info;
                info.host_entry = pthread_create_args[2];
                info.host_args = pthread_create_args[3];
                printf("Guest pthread_create: %p %p\n", info.host_entry, info.host_args);

                pthread_mutex_init(&info.mutex, NULL);
                pthread_mutex_lock(&info.mutex);
                pthread_cond_init(&info.cond, NULL);
                int ret = pthread_create(&info.thread, (pthread_attr_t *) pthread_create_args[1],
                                         pthread_create_entry, &info);
                if (ret == 0) {
                    pthread_cond_wait(&info.cond, &info.mutex);
                }
                pthread_mutex_unlock(&info.mutex);
                pthread_cond_destroy(&info.cond);
                pthread_mutex_destroy(&info.mutex);
                *pthread_create_ret = ret;

                // WARN: get host pthread_t
                break;
            }

            case X64NC_Result_ThreadExit: {
                void *ret = next_call[0];
                pthread_exit(ret);
                break;
            }

            default:
                break;
        }
        // Notify host to continue and wait for the next callback
        syscall_ret =
            syscall1(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_WaitForFinished);
    }
    return 0;
}

void x64nc_RegisterCallThunk(const char *signature, void *func) {
    void *a[] = {
        _const_cast(char *)(signature),
        func,
    };
    syscall2(X64NC_MAGIC_SYSCALL_INDEX, _reinterpret_cast(void *) X64NC_RegisterCallThunk, a);
}

void x64nc_ExtractVariadicList(const char *fmt, void **data_buf, char *types_buf) {
}

void x64nc_ExtractVariadicList_ScanF(const char *fmt, void **data_buf, char *types_buf) {
}