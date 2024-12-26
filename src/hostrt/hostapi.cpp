#include "hostapi.h"

#include <unordered_map>
#include <string>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <vector>

#include <link.h>

#include "x64nc_common.h"

struct X64NC_TranslatorApis {
    typedef void (*FP_ExecuteCallback)(void * /*thunk*/, void * /*callback*/, void * /*args*/, void * /*ret*/);
    typedef pthread_t (*FP_GetLastPThreadId)(void);
    typedef void (*FP_NotifyPThreadCreate)(pthread_t * /*thread*/, const pthread_attr_t * /*attr*/,
                                           void *(*) (void *) /*start_routine*/, void * /*arg*/, int * /*ret*/);
    typedef void (*FP_NotifyPThreadExit)(void * /*ret*/);

    FP_ExecuteCallback ExecuteCallback;
    FP_GetLastPThreadId GetLastPThreadId;
    FP_NotifyPThreadCreate NotifyPThreadCreate;
    FP_NotifyPThreadExit NotifyPThreadExit;
};

static inline std::string_view PathGetFileName(const std::string_view &path) {
    auto i = path.find_last_of('/');
    return path.substr(i + 1);
}

static std::vector<std::string_view> SplitString(const std::string_view &s, const std::string_view &delimiter) {
    std::vector<std::string_view> tokens;
    std::string::size_type start = 0;
    std::string::size_type end = s.find(delimiter);
    while (end != std::string::npos) {
        tokens.push_back(s.substr(start, end - start));
        start = end + delimiter.size();
        end = s.find(delimiter, start);
    }
    tokens.push_back(s.substr(start));
    return tokens;
}

static const char DefaultLibraryMappingFile[] = "/home/overworld/Documents/ccxxprojs/qemu-nc/.cache/x64nc_mappings.txt";

struct X64NC_HostRuntimeData {
    X64NC_TranslatorApis TranslatorApis;
    std::unordered_map<std::string, void *> CallbackThunks;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_G2D;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_G2H;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_D2G;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_D2H;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_H2G;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_H2D;

    X64NC_HostRuntimeData() {
        const char *library_mapping_file = getenv("X64NC_LIBRARY_MAPPING_FILE");
        if (library_mapping_file) {
            library_mapping_file = DefaultLibraryMappingFile;
        }
        std::ifstream file(library_mapping_file);
        if (file.is_open()) {
            std::string line;
            while (std::getline(file, line)) {
                if (line.empty()) {
                    continue;
                }
                if (line.front() == '#') {
                    continue;
                }
                auto items = SplitString(line, ":");
                if (items.size() != 3) {
                    continue;
                }

                LibraryPathIndexes_G2D[std::string(PathGetFileName(items[0]))] = items[1];
                LibraryPathIndexes_G2H[std::string(PathGetFileName(items[0]))] = items[2];
                LibraryPathIndexes_D2G[std::string(PathGetFileName(items[1]))] = items[0];
                LibraryPathIndexes_D2H[std::string(PathGetFileName(items[1]))] = items[2];
                LibraryPathIndexes_H2G[std::string(PathGetFileName(items[2]))] = items[0];
                LibraryPathIndexes_H2D[std::string(PathGetFileName(items[2]))] = items[1];
            }
        } else {
            printf("nc: failed to open library mapping file \"%s\".\n", library_mapping_file);
            std::abort();
        }
    }
};

static X64NC_HostRuntimeData HostRuntimeData;

static unsigned int host_audit_objopen(struct link_map *map, Lmid_t lmid, uintptr_t *cookie, const char *target) {
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

// static int var_foo = 114514;

static uintptr_t host_audit_symbind64(Elf64_Sym *sym, unsigned int ndx, uintptr_t *refcook, uintptr_t *defcook,
                                      unsigned int *flags, const char *symname) {
    // printf("Looking up symbol 64: %s, org: %p\n", symname, (void *) sym->st_value);
    // if (strcmp(symname, "var_foo") == 0) {
    //     return (uintptr_t) &var_foo;
    // }
    return sym->st_value;
}

// --------------------------------------------------------------------------------------
// QEMU emulator will call the following functions
void x64nc_HandleExtraGuestCall(int type, void *args[]) {
    switch (type) {
        case X64NC_LA_ObjOpen: {
            *(unsigned int *) args[4] =
                host_audit_objopen((link_map *) args[0], (Lmid_t) args[1], (uintptr_t *) args[2], (char *) args[3]);
            break;
        }

        case X64NC_LA_ObjClose:
            *(unsigned int *) args[2] = host_audit_objclose((link_map *) args[0], (uintptr_t *) args[1]);
            break;

        case X64NC_LA_PreInit:
            *(unsigned int *) args[2] = host_audit_preinit((link_map *) args[0], (uintptr_t *) args[1]);
            break;

        case X64NC_LA_SymBind:
            *(uintptr_t *) args[6] =
                host_audit_symbind64((Elf64_Sym *) args[0], (unsigned int) (uintptr_t) args[1], (uintptr_t *) args[2],
                                     (uintptr_t *) args[3], (unsigned int *) args[4], (char *) args[5]);
            break;

        case X64NC_AddCallbackThunk: {
            auto sign = (char *) (args[0]);
            HostRuntimeData.CallbackThunks[sign] = args[1];
            break;
        }

        case X64NC_SearchLibrary: {
            auto path = (char *) (args[0]);
            auto mode = (int) (uintptr_t) args[1];
            auto ret_ref = (const char **) args[2];
            *ret_ref = x64nc_SearchLibraryH(path, mode);
            break;
        }

        default:
            break;
    }
}

void *x64nc_GetTranslatorApis() {
    return &HostRuntimeData.TranslatorApis;
}

char *x64nc_SearchLibraryH(const char *path, int mode) {
    decltype(X64NC_HostRuntimeData::LibraryPathIndexes_G2H) *indexes;
    switch (mode) {
        case X64NC_SL_Mode_G2D:
            indexes = &HostRuntimeData.LibraryPathIndexes_G2D;
            break;
        case X64NC_SL_Mode_G2H:
            indexes = &HostRuntimeData.LibraryPathIndexes_G2H;
            break;
        case X64NC_SL_Mode_D2G:
            indexes = &HostRuntimeData.LibraryPathIndexes_D2G;
            break;
        case X64NC_SL_Mode_D2H:
            indexes = &HostRuntimeData.LibraryPathIndexes_D2H;
            break;
        case X64NC_SL_Mode_H2G:
            indexes = &HostRuntimeData.LibraryPathIndexes_H2G;
            break;
        case X64NC_SL_Mode_H2D:
            indexes = &HostRuntimeData.LibraryPathIndexes_H2D;
            break;
            break;
        default:
            return nullptr;
    }
    auto it = indexes->find(std::string(PathGetFileName(path)));
    if (it == indexes->end()) {
        return nullptr;
    }
    return it->second.data();
}
// --------------------------------------------------------------------------------------


// --------------------------------------------------------------------------------------
// Host libraries will call the following functions
void *x64nc_GetFPExecuteCallback() {
    return (void *) HostRuntimeData.TranslatorApis.ExecuteCallback;
}

void *x64nc_LookUpCallbackThunk(const char *sign) {
    auto it = HostRuntimeData.CallbackThunks.find(sign);
    if (it == HostRuntimeData.CallbackThunks.end()) {
        return nullptr;
    }
    return it->second;
}
// --------------------------------------------------------------------------------------

extern "C" X64NC_EXPORT int x64nc_pthread_create(pthread_t *__restrict thread, const pthread_attr_t *__restrict attr,
                                                 void *(*start_routine)(void *), void *__restrict arg) {
    int ret;
    HostRuntimeData.TranslatorApis.NotifyPThreadCreate(thread, attr, start_routine, arg, &ret);
    *thread = HostRuntimeData.TranslatorApis.GetLastPThreadId();
    return ret;
}

extern "C" X64NC_EXPORT void x64nc_pthread_exit(void *ret) {
    HostRuntimeData.TranslatorApis.NotifyPThreadExit(ret);
    __builtin_unreachable();
}