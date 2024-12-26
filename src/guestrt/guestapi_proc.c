#include "guestapi.h"

#include <pthread.h>

#include <stddef.h>
#include <stdio.h>

#include "syscall_helper.h"
#include "x64nc_common.h"

struct thread_info {
    pthread_t thread;
    pthread_mutex_t mutex;
    pthread_cond_t cond;

    void *host_entry;
    void *host_args;
};

static void *ThreadEntry(void *args) {
    struct thread_info *info = args;

    void *entry = info->host_entry;
    void *arg = info->host_args;

    /* Signal to the parent that we're ready.  */
    pthread_mutex_lock(&info->mutex);
    pthread_cond_broadcast(&info->cond);
    pthread_mutex_unlock(&info->mutex);
    /* Wait until the parent has finished initializing the tls state.  */

    void *ret;
    x64nc_CallNativeProc(entry, arg, &ret, X64NC_NP_Convention_ThreadEntry);
    return ret;
}

static void NativeCallServe(void *a) {
    void *next_call[8];

    // Call and wait for the potential callback request
    uint64_t syscall_ret = syscall3(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_CallNativeProc, a, next_call);
    while (syscall_ret != X64NC_NP_Result_Finished) {
        switch (syscall_ret) {
            case X64NC_NP_Result_Callback: {
                typedef void (*CallbackThunk)(void * /*callback*/, void * /*args*/, void * /*ret*/);
                CallbackThunk thunk = next_call[0];
                void *callback = next_call[1];
                void *args = next_call[2];
                void *ret = next_call[2];
                thunk(callback, args, ret);
                break;
            }

            case X64NC_NP_Result_PThreadCreate: {
                pthread_attr_t *attr = next_call[1];
                void *host_start_routine = next_call[2];
                void *host_args = next_call[3];
                int *ret_ref = next_call[4];

                struct thread_info info;
                info.host_entry = host_start_routine;
                info.host_args = host_args;
                pthread_mutex_init(&info.mutex, NULL);
                pthread_mutex_lock(&info.mutex);
                pthread_cond_init(&info.cond, NULL);

                // Create thread
                int ret = pthread_create(&info.thread, attr, ThreadEntry, &info);
                if (ret == 0) {
                    pthread_cond_wait(&info.cond, &info.mutex);
                }

                pthread_mutex_unlock(&info.mutex);
                pthread_cond_destroy(&info.cond);
                pthread_mutex_destroy(&info.mutex);
                *ret_ref = ret;

                // Host pthread id will be set in host runtime
                break;
            }

            case X64NC_NP_Result_PThreadExit: {
                void *ret = next_call[0];
                pthread_exit(ret);
                break;
            }

            default:
                break;
        }

        // Notify host to continue and wait for the next callback request
        syscall_ret = syscall1(X64NC_MAGIC_SYSCALL_INDEX, (void *) X64NC_ResumeNativeProc);
    }
}

void x64nc_CallNativeProc(void *func, void *args[], void *ret, int convention) {
    void *a[] = {
        func,
        args,
        ret,
        (void *) (intptr_t) convention,
    };
    NativeCallServe(a);
}