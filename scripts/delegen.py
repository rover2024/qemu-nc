# Usage: python delegen.py <symbols file> <header file> <library_name> [-o <output dir>] [-X <clang args>]

# Generates "x64nc_declarations.h",
#           "x64nc_delegate_guest_definitions.cpp"
#           "x64nc_delegate_host_definitions.cpp"
#           "<library_name>_callbacks.txt"

from __future__ import annotations

import sys
import os
import re
import io
import argparse
import shutil
import json

from clang.cindex import Config
from clang.cindex import Index
from clang.cindex import Cursor
from clang.cindex import CursorKind
from clang.cindex import Type
from clang.cindex import TypeKind
from clang.cindex import SourceRange
from clang.cindex import SourceLocation

from typing import Optional

class Global:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    resource_dir = os.path.join(script_dir, 'delegen_resources')
    config_path = os.path.join(script_dir, 'ncconfig.json')

    guest_cc: str
    guest_include_path: str
    guest_library_path: str
    guest_output_path: str
    
    host_cc: str
    host_include_path: str
    host_library_path: str
    host_output_path: str

sys.path.append(Global.script_dir)

from python.text import *
import python.clang as cl



def main():
    parser = argparse.ArgumentParser(description='Generate stub functions for given symbols.')
    parser.add_argument('-X', nargs=argparse.REMAINDER, metavar="<clang args>", default=[], help='Extra arguments to pass to Clang.')
    parser.add_argument('-o', type=str, metavar="<out>", required=False, help='Output directory name')
    parser.add_argument('symbols_file', type=str, help='File contains list of symbols.')
    parser.add_argument('header_file', type=str, help='Header file to parse.')
    parser.add_argument('library_name', type=str, help='Library name.')
    args = parser.parse_args()

    # Read configuration file
    with open(Global.config_path, 'r') as file:
        json_doc = json.load(file)

        # Set the path to the clang library
        Config.set_library_file(json_doc['libclang'])
        Global.guest_cc = json_doc['nativeCompat']['guest']['cc']
        Global.guest_include_path = json_doc['nativeCompat']['guest']['includePath']
        Global.guest_library_path = json_doc['nativeCompat']['guest']['libraryPath']
        Global.guest_output_path = json_doc['nativeCompat']['guest']['outputPath']
        Global.host_cc = json_doc['nativeCompat']['host']['cc']
        Global.host_include_path = json_doc['nativeCompat']['host']['includePath']
        Global.host_library_path = json_doc['nativeCompat']['host']['libraryPath']
        Global.host_output_path = json_doc['nativeCompat']['host']['outputPath']

    # Arguments
    symbols_file: str = args.symbols_file
    header_file: str = args.header_file
    library_name: str = args.library_name
    output_file_directory: str = args.o if args.o else f'{library_name}_src'

    input_include_dirs = cl.CommandLine.include_dirs(args.X)
    input_definitions = cl.CommandLine.defnitions(args.X)
    
    # Load symbols
    symbols_set = read_list_file_as_set(symbols_file)
    
    # Configure the index to parse the header files
    index = Index.create()
    translation_unit = index.parse(header_file, args=['-x', 'c'] + args.X)

    # Collect function declarations and types
    functions: dict[str, Cursor] = {}
    symbols_remaining = symbols_set
    all_types: list[Type] = []
    all_type_spellings: set[str] = set()
    c: Cursor
    for c in translation_unit.cursor.get_children():
        if c.kind == CursorKind.FUNCTION_DECL and c.spelling in symbols_remaining:
            # Scan types
            cl.scan_types(c.result_type, all_types, all_type_spellings)
            for arg in c.get_arguments():
                cl.scan_types(arg.type, all_types, all_type_spellings)
            
            # Collect function
            functions[c.spelling] = c
            symbols_remaining.remove(c.spelling)
    
    # Find function prototypes
    callback_types: list[Type] = []
    callback_type_spellings: set[str] = set()
    type: Type
    for type in all_types:
        type = cl.Typing.primitive(type).get_canonical()
        if cl.Typing.is_func_ptr(type):
            spelling: str = cl.TypeSpelling.func_type(type, True)
            if spelling in callback_type_spellings:
                continue
            callback_types.append(type)
            callback_type_spellings.add(spelling)

    # Generate declarations file
    with io.StringIO() as f:
        lines: list[str] = []
        with open(header_file, 'r') as file:
            for line in file:
                lines.append(line.replace('\n', ''))
        
        # Header content
        print("X64NC_EXTERN_C_BEGIN", file=f)
        for line in lines:
            print(line, file=f)
        print("X64NC_EXTERN_C_END", file=f)
        print("\n", file=f)

        # Functions
        f.write('#ifndef X64NC_API_FOREACH_PRE\n#define X64NC_API_FOREACH_PRE(F)\n#endif\n')
        f.write('#define X64NC_API_FOREACH(F) X64NC_API_FOREACH_PRE(F)')
        for spelling in functions.keys():
            f.write(f' \\\n    F({spelling})')
        f.write('\n\n')

        # Callbacks
        f.write('#ifndef X64NC_CALLBACK_FOREACH_PRE\n#define X64NC_CALLBACK_FOREACH_PRE(F)\n#endif\n')
        f.write('#define X64NC_CALLBACK_FOREACH(F) X64NC_CALLBACK_FOREACH_PRE(F)')
        for i in range(0, len(callback_types)):
            f.write(f' \\\n    F(\"{cl.TypeSpelling.func_type(callback_types[i], True)}\", __X64NC_CallbackThunk_{i + 1})')
        f.write('\n\n')

        declaration_file_content = cl.TypeSpelling.normalize_builtin(f.getvalue())
    
    # Generate guest file
    with io.StringIO() as f:
        # Generate function definitions
        for c in functions.values():
            type: Type = c.type
            return_type_spelling = cl.TypeSpelling.decl(c.result_type)
            args:list[Cursor] = list(c.get_arguments())

            # Generate function declaration
            decl_str = f'{return_type_spelling} {c.spelling} (' + \
                str(', ').join([f"{cl.TypeSpelling.decl(args[i].type)} {f'_arg{i + 1}'}" for i in range(0, len(args))])
            if type.kind == TypeKind.FUNCTIONPROTO and type.is_function_variadic():
                decl_str += ', ...'
            decl_str += ')'
            print(decl_str, file=f)

            # Generate function body
            print("{", file=f)
            
            arg_ptr_array_str = str(', ').join(f"_R(_arg{i + 1})" for i in range(0, len(args)))
            arg_ptr_array_str = '{' + arg_ptr_array_str + '}'
            print(f'    void *_args[] = {arg_ptr_array_str};', file=f)
            
            if return_type_spelling != 'void':
                print(f'    {return_type_spelling} _ret;', file=f)
                print(f'    x64nc_CallNativeProc(DynamicApis_p{c.spelling}, _args, &_ret, 0);', file=f)
                print(f'    return _ret;', file=f)
            else:
                print(f'    x64nc_CallNativeProc(DynamicApis_p{c.spelling}, _args, NULL, 0);', file=f)

            print('}\n', file=f)

        # Print hint of undefined functions
        for symbol in symbols_remaining:
            print(f'// No definition found for {symbol}', file=f)
        
        print("\n", file=f)

        # Generate callback thunks
        for i in range(0, len(callback_types)):
            type: Type = callback_types[i]
            return_type_spelling = cl.TypeSpelling.decl(type.get_result())
            arg_types:list[Type] = list(type.argument_types())

            # Generate function declaration
            print(f"static void __X64NC_CallbackThunk_{i + 1}(void *_callback, void *_args[], void *_ret)", file=f)

            # Generate function body
            print("{", file=f)

            if return_type_spelling != 'void':
                print(f'    *(__typeof__({return_type_spelling}) *) _ret =', file=f)

            arg_dereferenced_list_str = str(', ').join([ \
                f"*(__typeof__({cl.TypeSpelling.decl(arg_types[i])}) *) {f'_args[{i}]'}" for i in range(0, len(arg_types))])
            print(f'    ((__typeof__({type.get_canonical().spelling}) *) _callback) ({arg_dereferenced_list_str});', file=f)
            print('}\n', file=f)
        
        guest_delegate_file_content = cl.TypeSpelling.normalize_builtin(f.getvalue())
    
    # Generate host file
    with io.StringIO() as f:
        print('X64NC_EXTERN_C_BEGIN', file=f)
        print('\n', file=f)
        for c in functions.values():
            return_type_spelling = cl.TypeSpelling.decl(c.result_type)
            args:list[Cursor] = list(c.get_arguments())
            
            # Generate function declaration
            print(f"X64NC_DECL_EXPORT void my_{c.spelling}(void *_args[], void *_ret)", file=f)

            # Generate function body
            print("{", file=f)

            if return_type_spelling != 'void':
                print(f'    *(__typeof__({return_type_spelling}) *) _ret =', file=f)

            arg_dereferenced_list_str = str(', ').join([ \
                f"*(__typeof__({cl.TypeSpelling.decl(args[i].type)}) *) {f'_args[{i}]'}" for i in range(0, len(args))])
            print(f'    DynamicApis_p{c.spelling}({arg_dereferenced_list_str});', file=f)
            print('}\n', file=f)
        print('\n', file=f)
        print('X64NC_EXTERN_C_END', file=f)
        
        host_delegate_file_content = cl.TypeSpelling.normalize_builtin(f.getvalue())

    # Write files
    if not os.path.exists(output_file_directory):
        os.makedirs(output_file_directory)

    with open(os.path.join(output_file_directory, '_x64nc_declarations.h'), mode='w') as f:
        f.write(declaration_file_content)

    with open(os.path.join(output_file_directory, '_x64nc_delegate_guest_definitions.c'), mode='w') as f:
        f.write(guest_delegate_file_content)

    with open(os.path.join(output_file_directory, '_x64nc_delegate_host_definitions.c'), mode='w') as f:
        f.write(host_delegate_file_content)

    with open(os.path.join(output_file_directory, f'{library_name}_callbacks.txt'), mode='w') as f:
        f.write("\n".join(callback_type_spellings))

    # Copy templates
    files = [os.path.join(Global.resource_dir, file) for file in os.listdir(Global.resource_dir)]
    for file in files:
        if os.path.isfile(file):
            shutil.copy(file, output_file_directory)
    
    # Rewrite Makefile
    replace_file_placeholders(os.path.join(output_file_directory, 'Makefile'),
        { 
            'NC_USER_LIBRARY_NAME': library_name,
            'NC_USER_INCLUDE_PATHS': ' '.join(input_include_dirs),
            'NC_USER_DEFINITIONS': ' '.join(input_definitions),
            'NC_GUEST_CC': Global.guest_cc,
            'NC_GUEST_RUNTIME_INCLUDE_PATH': Global.guest_include_path,
            'NC_GUEST_RUNTIME_LINK_PATH': Global.guest_library_path,
            'NC_GUEST_OUTPUT_PATH': Global.guest_output_path,
            'NC_HOST_CC': Global.host_cc,
            'NC_HOST_RUNTIME_INCLUDE_PATH': Global.host_include_path,
            'NC_HOST_RUNTIME_LINK_PATH': Global.host_library_path,
            'NC_HOST_OUTPUT_PATH': Global.host_output_path,
        }
    )


if __name__ == '__main__':
    main()