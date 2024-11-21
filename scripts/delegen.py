# Usage: python delegen.py <symbols file> <header file> [-I<dir>] [-D<FOO=bar>] [-o <output dir>]

# Generates "x64nc_declarations.h",
#           "x64nc_delegate_guest_definitions.cpp"
#           "x64nc_delegate_host_definitions.cpp"

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

from .util import read_list_file_as_set
from .util import replace_file_placeholders
from .util import clang_scan_type


class Global:
    clang_library_dir = "/lib/x86_64-linux-gnu/libclang-18.so"
    resource_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delegen_resources')


def main():
    parser = argparse.ArgumentParser(description='Generate stub functions for given symbols.')
    parser.add_argument('-I', type=str, action='append', metavar="<dir>", default=[], help='Include path for headers.')
    parser.add_argument('-D', type=str, action='append', metavar="<definition>", default=[], help='Macro definitions.')
    parser.add_argument('-o', type=str, metavar="<out>", required=False, help='Output directory name')
    parser.add_argument('symbols_file', type=str, help='File with symbols.')
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
                                   [f'-D{m}' for m in args.D])

    # Collect function declarations and types
    functions: dict[str, str] = {}
    symbols_remaining = symbols_set
    all_types: list[Type] = []
    all_type_spellings: set[str] = set()
    c: Cursor
    for c in translation_unit.cursor.get_children():
        if c.kind == CursorKind.FUNCTION_DECL and c.spelling in symbols_remaining:
            # Scan types
            clang_scan_type(c.result_type, all_types, all_type_spellings)
            for arg in c.get_arguments():
                clang_scan_type(arg.type, all_types, all_type_spellings)
            
            # Collect function
            functions[c.spelling] = c
            symbols_remaining.remove(c.spelling)
    
    # Generate declarations file
    function_pointer_alias: dict[str, str] = {}
    with io.StringIO() as f:
        lines: list[str] = []
        with open(header_file, 'r') as file:
            for line in file:
                lines.append(line.strip())
        
        # Header content
        print("extern \"C\" {", file=f)
        for line in lines:
            print(line, file=f)
        print("}\n", file=f)

        # Using declarations
        i = 1
        for type in all_types:
            if is_function_pointer(type):
                type_alias = f'__X64NC_{library_name}_TYPE_ALIAS_{i}'
                function_pointer_alias[type.get_canonical().spelling] = type_alias
                print(f"using {type_alias} = {type.spelling};", file=f)
                i += 1
        f.write('\n')
        
        # Functions
        f.write('#define X64NC_API_FOREACH_FUNCTION(F)')
        for fname, _ in functions.items():
            f.write(f' \\\n    F({fname})')
        f.write('\n')
        
        declaration_file_content = f.getvalue()
    
    def to_type_str(type: Type) -> str:
        if is_function_pointer(type):
            type_str = function_pointer_alias[type.get_canonical().spelling]
        elif type.kind == TypeKind.CONSTANTARRAY:
            type_str = type.element_type.spelling + " *"
        else:
            type_str = type.spelling
        return type_str
    
    # Generate guest file
    with io.StringIO() as f:
        for fname, c in functions.items():
            func_type: Type = c.type
            arg_list: list[tuple[str, str]] = []
            i = 1
            for arg in c.get_arguments():
                arg_list.append((to_type_str(arg.type), f'_arg{i}'))
                i += 1
            
            return_type_str = to_type_str(c.result_type)
            arg_list_str = str(', ').join([f'{t[0]} {t[1]}' for t in arg_list])
            if func_type.is_function_variadic():
                print(f"{return_type_str} {fname} ({arg_list_str}, ...)", file = f)
            else:
                print(f"{return_type_str} {fname} ({arg_list_str})", file = f)
            print("{", file = f)
            
            args_arrange = ", ".join(f"_arg{i}" for i in range(1, len(arg_list) + 1))
            print(f'    auto _args = get_addresses_of_parameters({args_arrange});', file=f)
            
            if return_type_str != 'void':
                print(f"    {return_type_str} _ret = {{}};", file=f)
                print(f'    x64nc_CallNativeProc(DynamicApis::p{c.spelling}, _args.data(), &_ret);', file=f)
                print(f'    return _ret;', file=f)
            else:
                print(f'    x64nc_CallNativeProc(DynamicApis::p{c.spelling}, _args.data(), nullptr);', file=f)

            print('}\n', file=f)

        for symbol in symbols_remaining:
            print(f'// No definition found for {symbol}', file=f)
        
        guest_delegate_file_content = f.getvalue()
    
    # Generate host file
    with io.StringIO() as f:
        for fname, c in functions.items():
            sr: SourceRange = c.extent
            print(f"extern \"C\" __attribute__((visibility(\"default\"))) void my_{fname}(void *_args, void *_ret)", file=f)
            print("{", file = f)
            print(f"call_function2(DynamicApis::p{fname}, (void **) _ret, _args);", file=f)
            print('}\n', file=f)
        
        host_delegate_file_content = f.getvalue()

    # Write files
    if not os.path.exists(output_file_directory):
        os.makedirs(output_file_directory)

    with open(os.path.join(output_file_directory, 'x64nc_declarations.h'), mode='w') as f:
        f.write(declaration_file_content)

    with open(os.path.join(output_file_directory, 'x64nc_delegate_guest_definitions.cpp'), mode='w') as f:
        f.write(guest_delegate_file_content)

    with open(os.path.join(output_file_directory, 'x64nc_delegate_host_definitions.cpp'), mode='w') as f:
        f.write(host_delegate_file_content)

    # Copy templates
    files = [os.path.join(Global.resource_dir, file) for file in os.listdir(Global.resource_dir)]
    for file in files:
        if os.path.isfile(file):
            shutil.copy(file, output_file_directory)
    
    # Rewrite Makefile
    replace_file_placeholders(os.path.join(output_file_directory, 'Makefile'), { 'LIBRARY_NAME': library_name })


if __name__ == '__main__':
    main()