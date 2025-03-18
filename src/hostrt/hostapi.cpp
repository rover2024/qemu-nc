#include "hostapi.h"

#include <unordered_map>
#include <string>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <vector>

#include <link.h>

#include "x64nc_common.h"

#include "json11.hpp"

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

static void StringReplaceAll(std::string &str, const std::string &from, const std::string &to) {
    if (from.empty())
        return;
    size_t start_pos = 0;
    while ((start_pos = str.find(from, start_pos)) != std::string::npos) {
        str.replace(start_pos, from.length(), to);
        start_pos += to.length(); // In case 'to' contains 'from', like replacing 'x' with 'yx'
    }
}

static const char DefaultLibraryMappingFile[] = "/home/overworld/Documents/ccxxprojs/qemu-nc/.cache/x64nc_mappings.txt";

struct X64NC_HostRuntimeData {
    X64NC_TranslatorApis TranslatorApis;
    std::unordered_map<std::string, void *> CallbackThunks;

    // mappings
    std::unordered_map<std::string, std::string> LibraryPathIndexes_G2H;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_G2N;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_H2G;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_H2N;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_N2G;
    std::unordered_map<std::string, std::string> LibraryPathIndexes_N2H;

    void readMappingItem(const std::string &key, const json11::Json &val) {
        if (!val.is_object()) {
            return;
        }
        const auto &obj = val.object_items();

        std::string pathG, pathH, pathN;

        auto it = obj.find("G");
        if (it == obj.end() || !it->second.is_string())
            return;
        pathG = escape_mapping_path(it->second.string_value());
        it = obj.find("H");
        if (it == obj.end() || !it->second.is_string())
            return;
        pathH = escape_mapping_path(it->second.string_value());
        it = obj.find("N");
        if (it == obj.end() || !it->second.is_string())
            return;
        pathN = escape_mapping_path(it->second.string_value());

        if (!(key.size() >= 1 && key.back() == '^')) {
            LibraryPathIndexes_G2H[std::string(PathGetFileName(pathG))] = pathH;
            LibraryPathIndexes_G2N[std::string(PathGetFileName(pathG))] = pathN;
            LibraryPathIndexes_H2G[std::string(PathGetFileName(pathH))] = pathG;
            LibraryPathIndexes_H2N[std::string(PathGetFileName(pathH))] = pathN;
        }
        LibraryPathIndexes_N2G[std::string(PathGetFileName(pathN))] = pathG;
        LibraryPathIndexes_N2H[std::string(PathGetFileName(pathN))] = pathH;
    }

    static std::string escape_mapping_path(std::string path) {
        static std::string home = getenv("X64NC_HOME");
        StringReplaceAll(path, "@", home);
        return path;
    }

    X64NC_HostRuntimeData() {
        const char *library_mapping_file = getenv("X64NC_LIBRARY_MAPPING_FILE");
        if (!library_mapping_file) {
            library_mapping_file = DefaultLibraryMappingFile;
        }
        std::ifstream file(library_mapping_file);
        if (file.is_open()) {
            std::stringstream ss;
            ss << file.rdbuf();

            std::string err;
            auto json = json11::Json::parse(ss.str(), err);
            if (!err.empty()) {
                printf("nc: failed to parse library mapping file \"%s\": %s\n", library_mapping_file, err.c_str());
                std::abort();
            }

            if (json.is_object()) {
                const auto &objDoc = json.object_items();
                for (const auto &item : objDoc) {
                    readMappingItem(item.first, item.second);
                }
            } else if (json.is_array()) {
                const auto &objArr = json.array_items();
                for (const auto &item : objArr) {
                    readMappingItem({}, item);
                }
            } else {
                printf("nc: unexpected format \"%s\"\n", library_mapping_file);
                std::abort();
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

static int var_foo = 114514;

static uintptr_t host_audit_symbind64(Elf64_Sym *sym, unsigned int ndx, uintptr_t *refcook, uintptr_t *defcook,
                                      unsigned int *flags, const char *symname) {
    printf("Looking up symbol 64: %s, org: %p\n", symname, (void *) sym->st_value);
    if (strcmp(symname, "var_foo") == 0) {
        return (uintptr_t) &var_foo;
    }
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
    x64nc_debug("HRT: search library: path=\"%s\", mode=%d\n", path, mode);
    decltype(X64NC_HostRuntimeData::LibraryPathIndexes_G2N) *indexes;
    switch (mode) {
        case X64NC_SL_Mode_G2H:
            indexes = &HostRuntimeData.LibraryPathIndexes_G2H;
            break;
        case X64NC_SL_Mode_G2N:
            indexes = &HostRuntimeData.LibraryPathIndexes_G2N;
            break;
        case X64NC_SL_Mode_H2G:
            indexes = &HostRuntimeData.LibraryPathIndexes_H2G;
            break;
        case X64NC_SL_Mode_H2N:
            indexes = &HostRuntimeData.LibraryPathIndexes_H2N;
            break;
        case X64NC_SL_Mode_N2G:
            indexes = &HostRuntimeData.LibraryPathIndexes_N2G;
            break;
        case X64NC_SL_Mode_N2H:
            indexes = &HostRuntimeData.LibraryPathIndexes_N2H;
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

    // printf("%s: %lx\n", __func__, *thread);

    auto self = pthread_self();
    auto last = HostRuntimeData.TranslatorApis.GetLastPThreadId();
    return ret;
}

extern "C" X64NC_EXPORT void x64nc_pthread_exit(void *ret) {
    HostRuntimeData.TranslatorApis.NotifyPThreadExit(ret);
    __builtin_unreachable();
}