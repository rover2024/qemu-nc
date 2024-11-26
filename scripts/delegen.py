# Usage: python delegen.py <symbols file> <header file> <library_name>
#                          [-I<dir>] [-D<FOO=bar>] [-F <extra flags>] [-o <output dir>]

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

from clang.cindex import Config
from clang.cindex import Index
from clang.cindex import Cursor
from clang.cindex import CursorKind
from clang.cindex import Type
from clang.cindex import TypeKind
from clang.cindex import SourceRange
from clang.cindex import SourceLocation

from typing import Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from python.text import *
import python.clang as cl


class Global:
    clang_library_dir = "/lib/x86_64-linux-gnu/libclang-18.so"
    resource_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delegen_resources')


def main():
    parser = argparse.ArgumentParser(description='Generate stub functions for given symbols.')
    parser.add_argument('-I', type=str, action='append', metavar="<dir>", default=[], help='Include path for headers.')
    parser.add_argument('-D', type=str, action='append', metavar="<definition>", default=[], help='Macro definitions.')
    parser.add_argument('-F', type=str, action='append', metavar="<extra flags>", default=[], help='Extra flags for the preprocessor.')
    parser.add_argument('-o', type=str, metavar="<out>", required=False, help='Output directory name')
    parser.add_argument('symbols_file', type=str, help='File contains list of symbols.')
    parser.add_argument('header_file', type=str, help='Header file to parse.')
    parser.add_argument('library_name', type=str, help='Library name.')
    args = parser.parse_args()

    # Set the path to the clang library
    Config.set_library_file(Global.clang_library_dir)

    # Arguments
    symbols_file: str = args.symbols_file
    header_file: str = args.header_file
    library_name: str = args.library_name
    output_file_directory: str = args.o if args.o else f'{library_name}_src'
    
    # Load symbols
    symbols_set = read_list_file_as_set(symbols_file)
    
    # Configure the index to parse the header files
    index = Index.create()
    translation_unit = index.parse(header_file, args=['-x', 'c'] + 
                                   [f'-I{path}' for path in args.I] + 
                                   [f'-D{m}' for m in args.D] + args.F)

    # Collect function declarations and types
    functions: dict[str, str] = {}
    symbols_remaining = symbols_set
    all_types: list[Type] = []
    all_type_spellings: set[str] = set()
    c: Cursor
    for c in translation_unit.cursor.get_children():
        if c.kind == CursorKind.FUNCTION_DECL and c.spelling in symbols_remaining:
            # Scan types
            cl.scan_type(c.result_type, all_types, all_type_spellings)
            for arg in c.get_arguments():
                cl.scan_type(arg.type, all_types, all_type_spellings)
            
            # Collect function
            functions[c.spelling] = c
            symbols_remaining.remove(c.spelling)
    
    # Find function prototypes
    callback_types: list[Type] = []
    callback_type_spellings: set[str] = set()
    for type in all_types:
        type: Type = cl.primordial_type(type).get_canonical()
        if type.kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]:
            spelling: str = cl.types.func_type_to_str(type, True)
            if spelling in callback_type_spellings:
                continue
            callback_types.append(type)
            callback_type_spellings.add(spelling)

    # Generate declarations file
    with io.StringIO() as f:
        lines: list[str] = []
        with open(header_file, 'r') as file:
            for line in file:
                lines.append(line.strip())
        
        # Header content
        print("X64NC_EXTERN_C_BEGIN", file=f)
        for line in lines:
            print(line, file=f)
        print("X64NC_EXTERN_C_END", file=f)
        print("\n", file=f)

        # Functions
        f.write('#define X64NC_API_FOREACH(F)')
        for fname, _ in functions.items():
            f.write(f' \\\n    F({fname})')
        f.write('\n\n')

        # Callbacks
        f.write('#define X64NC_CALLBACK_FOREACH(F)')
        for i in range(0, len(callback_types)):
            f.write(f' \\\n    F(\"{cl.types.func_type_to_str(callback_types[i])}\", __QEMU_NC_CallbackThunk_{i + 1})')
        f.write('\n\n')

        declaration_file_content = f.getvalue()
    
    # Generate guest file
    with io.StringIO() as f:
        for fname, c in functions.items():
            type: Type = c.type
            return_type_str = cl.types.to_str(c.result_type)
            args:list[Cursor] = list(c.get_arguments())
            arg_list_str = str(', ').join([f"{cl.types.to_str(args[i].type)} {f'_arg{i + 1}'}" for i in range(0, len(args))])
            
            if type.is_function_variadic():
                print(f"{return_type_str} {fname} ({arg_list_str}, ...)", file=f)
            else:
                print(f"{return_type_str} {fname} ({arg_list_str})", file=f)
            print("{", file=f)
            
            args_arrange = ", ".join(f"_R(_arg{i + 1})" for i in range(0, len(args)))
            print(f'    void *_args[] = {{{args_arrange}}};', file=f)
            
            if return_type_str != 'void':
                print(f"    {return_type_str} _ret;", file=f)
                print(f'    x64nc_CallNativeProc(DynamicApis_p{c.spelling}, _args, &_ret);', file=f)
                print(f'    return _ret;', file=f)
            else:
                print(f'    x64nc_CallNativeProc(DynamicApis_p{c.spelling}, _args, NULL);', file=f)

            print('}\n', file=f)

        for symbol in symbols_remaining:
            print(f'// No definition found for {symbol}', file=f)
        
        print("\n", file=f)

        for i in range(0, len(callback_types)):
            type: Type = callback_types[i]
            return_type_str = cl.types.to_str(type.get_result())
            arg_types:list[Type] = list(type.argument_types())

            print(f"static void __QEMU_NC_CallbackThunk_{i + 1}(void *_callback, void *_args[], void *_ret)", file=f)
            print("{", file=f)
            if return_type_str != 'void':
                print(f'    *(__typeof__({return_type_str}) *) _ret =', file=f)
            arg_list_str = str(', ').join([f"*(__typeof__({cl.types.to_str(arg_types[i])}) *) {f'_args[{i}]'}" for i in range(0, len(arg_types))])
            print(f'    ((__typeof__({type.get_canonical().spelling}) *) _callback) ({arg_list_str});', file=f)
            print('}\n', file=f)
        
        guest_delegate_file_content = f.getvalue()
    
    # Generate host file
    with io.StringIO() as f:
        print('X64NC_EXTERN_C_BEGIN', file=f)
        print('\n', file=f)
        for fname, c in functions.items():
            return_type_str = cl.types.to_str(c.result_type)
            args:list[Cursor] = list(c.get_arguments())
            
            print(f"X64NC_DECL_EXPORT void my_{fname}(void *_args[], void *_ret)", file=f)
            print("{", file=f)
            if return_type_str != 'void':
                print(f'    *(__typeof__({return_type_str}) *) _ret =', file=f)
            arg_list_str = str(', ').join([f"*(__typeof__({cl.types.to_str(args[i].type)}) *) {f'_args[{i}]'}" for i in range(0, len(args))])
            print(f'    DynamicApis_p{fname}({arg_list_str});', file=f)
            print('}\n', file=f)
        print('\n', file=f)
        print('X64NC_EXTERN_C_END', file=f)
        
        host_delegate_file_content = f.getvalue()

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
    makefile_template = os.path.join(output_file_directory, 'Makefile.in')
    replace_file_placeholders(makefile_template, \
                              { 'LIBRARY_NAME': library_name }, os.path.join(output_file_directory, 'Makefile'))
    os.remove(makefile_template)


if __name__ == '__main__':
    main()