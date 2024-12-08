#include "hostapi.h"

#include <unordered_map>
#include <string>
#include <cstdio>
#include <cstring>

#include <link.h>

#include "x64nc_common.h"

typedef void (*X64NC_HostExecuteCallback)(void * /*thunk*/, void * /*callback*/, void * /*args*/,
                                          void * /*ret*/);

typedef void (*X64NC_HostExtraEvent)(int /*num*/, void * /*args*/);

typedef pthread_t (*X64NC_GetHostLastThreadId)();

static X64NC_HostExecuteCallback m_hec;
static X64NC_HostExtraEvent m_hee;
static X64NC_GetHostLastThreadId m_ghlti;
static decltype(&pthread_create) m_org_pthread_create;
static decltype(&pthread_exit) m_org_pthread_exit;

static std::unordered_map<std::string, void *> m_thunks;

static unsigned int host_audit_objopen(struct link_map *map, Lmid_t lmid, uintptr_t *cookie,
                                       const char *target) {
    printf("Loading dynamic library: %s %s\n", map->l_name, target);
    return LA_FLG_BINDTO | LA_FLG_BINDFROM;
}

static unsigned int host_audit_objclose(struct link_map *map, uintptr_t *cookie) {
    printf("Closing dynamic library: %s\n", map->l_name);
    return 0;
}

static unsigned int host_audit_preinit(struct link_map *map, uintptr_t *cookie) {
    printf("Init dynamic library: %s\n", map->l_name);
    return 0;
}

static int var_foo = 114514;

static uintptr_t host_audit_symbind64(Elf64_Sym *sym, unsigned int ndx, uintptr_t *refcook,
                                      uintptr_t *defcook, unsigned int *flags,
                                      const char *symname) {
    printf("Looking up symbol 64: %s, org: %p\n", symname, (void *) sym->st_value);
    if (strcmp(symname, "var_foo") == 0) {
        return (uintptr_t) &var_foo;
    }
    return sym->st_value;
}

// --------------------------------------------------------------------------------------
// QEMU emulator will call the following functions

extern "C" X64NC_EXPORT void _QEMU_NC_SetThunk(int id, void *thunk) {
    switch (id) {
        case X64NC_Thunk_HostExecuteCallback:
            m_hec = reinterpret_cast<X64NC_HostExecuteCallback>(thunk);
            break;
        case X64NC_Thunk_HostExtraEvent:
            m_hee = reinterpret_cast<X64NC_HostExtraEvent>(thunk);
            break;
        case X64NC_Thunk_GetHostLastThreadId:
            m_ghlti = reinterpret_cast<X64NC_GetHostLastThreadId>(thunk);
            break;
        case X64NC_Thunk_ThreadCreate:
            m_org_pthread_create = reinterpret_cast<decltype(m_org_pthread_create)>(thunk);
            break;
        case X64NC_Thunk_ThreadExit:
            m_org_pthread_exit = reinterpret_cast<decltype(m_org_pthread_exit)>(thunk);
            break;
        default:
            break;
    }
}

extern "C" X64NC_EXPORT void _QEMU_NC_HandleExtraGuestCall(int type, void **args) {
    switch (type) {
        case X64NC_LA_ObjOpen: {
            *(unsigned int *) args[4] = host_audit_objopen((link_map *) args[0], (Lmid_t) args[1],
                                                           (uintptr_t *) args[2], (char *) args[3]);
            break;
        }

        case X64NC_LA_ObjClose:
            *(unsigned int *) args[2] =
                host_audit_objclose((link_map *) args[0], (uintptr_t *) args[1]);
            break;

        case X64NC_LA_PreInit:
            *(unsigned int *) args[2] =
                host_audit_preinit((link_map *) args[0], (uintptr_t *) args[1]);
            break;

        case X64NC_LA_SymBind:
            *(uintptr_t *) args[6] = host_audit_symbind64(
                (Elf64_Sym *) args[0], (unsigned int) (uintptr_t) args[1], (uintptr_t *) args[2],
                (uintptr_t *) args[3], (unsigned int *) args[4], (char *) args[5]);
            break;

        case X64NC_RegisterCallThunk: {
            m_thunks.insert(std::make_pair(static_cast<char *>(args[0]), args[1]));
            break;
        }

        default:
            break;
    }
}

// --------------------------------------------------------------------------------------


// --------------------------------------------------------------------------------------
// Host libraries will call the following functions

void QEMU_NC_CallHostExecuteCallback(void *thunk, void *callback, void *args, void *ret) {
    m_hec(thunk, callback, args, ret);
}

void *QEMU_NC_GetHostExecuteCallback() {
    return (void *) m_hec;
}

void *QEMU_NC_LookUpGuestThunk(const char *sign) {
    auto it = m_thunks.find(sign);
    if (it == m_thunks.end()) {
        return nullptr;
    }
    return it->second;
}

// --------------------------------------------------------------------------------------
extern "C" X64NC_EXPORT int my_pthread_create(pthread_t *__restrict thread,
                                           const pthread_attr_t *__restrict attr,
                                           void *(*start_routine)(void *), void *__restrict arg) {
    printf("Call pthread_create: %p %p\n", start_routine, arg);
    // __asm volatile("ud2");
    void *pthread_create_args[] = {
        thread,
        const_cast<pthread_attr_t *>(attr),
        (void *) start_routine,
        arg,
    };
    int ret;
    void *event_args[] = {
        pthread_create_args,
        &ret,
    };
    m_hee(X64NC_Result_ThreadCreate, event_args);
    *thread = m_ghlti();
    printf("Call pthread_create success: %lx\n", *thread);
    return ret;
}

extern "C" X64NC_EXPORT void my_pthread_exit(void *ret) {
    m_hee(X64NC_Result_ThreadExit, ret);

    __builtin_unreachable();
}