# Usage: python cfiadd.py <source file> [-I<dir>] [-D<FOO=bar>] [-F <extra flags>] [-o output]

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

import python.clang as cl
from python.text import *


class Global:
    clang_library_dir = "/lib/x86_64-linux-gnu/libclang-18.so"


class CheckGuardData:
    def __init__(self):
        self.name: str
        self.type: Type
        self.extent: SourceRange


def clang_reveal_call_expr(c: Cursor) -> tuple[Optional[Cursor], Type]:
    # input is CALL_EXPR
    c = list(c.get_children())[0]
    nested_level = 0
    while True:
        if c.kind in [CursorKind.UNEXPOSED_EXPR, CursorKind.PAREN_EXPR]:
            # extract
            c = list(c.get_children())[0]
            continue
        elif c.kind in [CursorKind.CALL_EXPR]:
            # extract
            c = list(c.get_children())[0]
            nested_level += 1
            continue
        elif c.kind in [CursorKind.BINARY_OPERATOR, CursorKind.CONDITIONAL_OPERATOR]:
            # get result of the last one
            c = list(c.get_children())[-1]
            continue
        elif c.kind in [CursorKind.MEMBER_REF_EXPR, CursorKind.DECL_REF_EXPR]:
            # get reference
            c = c.referenced
            break
        elif c.kind in [CursorKind.CSTYLE_CAST_EXPR]:
            break
        else:
            raise TypeError(f"Unexpected cursor kind: {c.kind}")

    if nested_level == 0:
        return c, c.type.get_canonical()

    type: Type = c.type
    while nested_level > 0:
        type = type.get_canonical().get_result()
        nested_level -= 1

    return None, type.get_canonical()


def main():
    parser = argparse.ArgumentParser(description='Add CFI check guard for function pointers.')
    parser.add_argument('-I', type=str, action='append', metavar="<dir>", default=[], help='Include path for headers.')
    parser.add_argument('-D', type=str, action='append', metavar="<definition>", default=[], help='Macro definitions.')
    parser.add_argument('-F', type=str, action='append', metavar="<extra flags>", default=[], help='Extra flags for the preprocessor.')
    parser.add_argument('-o', type=str, metavar="<out>", required=False, help='Output file name')
    parser.add_argument('source_file', type=str, help='Source file to process.')
    args = parser.parse_args()

    # Set the path to the clang library
    Config.set_library_file(Global.clang_library_dir)

    # Arguments
    source_file: str = args.source_file
    output_file: str = args.o if args.o else source_file

    # Configure the index to parse the header files
    index = Index.create()
    translation_unit = index.parse(source_file, args=['-x', 'c'] + 
                                   [f'-I{path}' for path in args.I] + 
                                   [f'-D{m}' for m in args.D] + args.F)
    
    # Collect function pointer positions
    function_pointers: list[Cursor] = []
    def scan_func_ptr(c: Cursor):
        if c.kind == CursorKind.CALL_EXPR:
            function_pointers.append(c)
        for child in c.get_children():
            scan_func_ptr(child)
    scan_func_ptr(translation_unit.cursor)

    with open(source_file, mode='r') as f:
        source_code = f.readlines()

    def get_source_range(range: SourceRange) -> str:
        start: SourceLocation = range.start
        end: SourceLocation = range.end
        cur_line = start.line - 1
        cur_column = start.column - 1
        res = ''
        while(cur_line < end.line - 1):
            res += source_code[cur_line][cur_column:] + ' '
            cur_line += 1
            cur_column = 0
        res += source_code[cur_line][cur_column:end.column - 1]
        return res
    
    def replace_source_range(range: SourceRange, s: str):
        start: SourceLocation = range.start
        end: SourceLocation = range.end
        cur_line = start.line - 1
        cur_column = start.column - 1
        while(cur_line < end.line - 1):
            source_code[cur_line] = source_code[cur_line][:cur_column]
            cur_line += 1
            cur_column = 0
        source_code[cur_line] = source_code[cur_line][0:cur_column] +  s + source_code[cur_line][end.column - 1:]

    # Process source code
    check_guards: list[CheckGuardData] = []
    existing_signatures: dict[str, int] = {} # signature -> index in `check_guards`

    for i in range(0, len(function_pointers)):
        c:Cursor = function_pointers[len(function_pointers) - 1 - i]
        # print(f'[{i + 1}]')
        # cl.traverse_cursor(c, 0)
        # print(" ")

        reveal_result = clang_reveal_call_expr(c)
        cursor: Optional[Cursor] = reveal_result[0]
        type: Type = reveal_result[1]

        if cursor and cursor.kind == CursorKind.FUNCTION_DECL:
            continue
        if type.kind == TypeKind.POINTER:
            type = type.get_pointee()
        if not type.kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]:
            continue

        children:list[Cursor] = list(c.get_children())
        if not children or len(children) < 2:
            continue
        func_ptr = children[0]
        first_arg = children[1]

        # Prepend first argument
        start: SourceLocation = first_arg.extent.start
        line = source_code[start.line - 1]
        line = line[:start.column - 1] + get_source_range(func_ptr.extent) + ', ' + line[start.column - 1:]
        source_code[start.line - 1] = line

        # Replace callee
        canonical_spelling:str = type.spelling
        if canonical_spelling in existing_signatures:
            name = check_guards[existing_signatures[canonical_spelling]].name
        else:
            name = f'__QEMU_NC_CHECK_GUARD_{len(existing_signatures) + 1}'
            existing_signatures[canonical_spelling] = len(check_guards)
        replace_source_range(func_ptr.extent, name)

        cg = CheckGuardData()
        cg.name = name
        cg.type = type
        cg.extent = func_ptr.extent
        check_guards.append(cg)

    # Generate CFI definitions
    check_guard_declarations: dict[str, str] = {}
    with io.StringIO() as f:
        print('#include <stdint.h>', file=f)
        print('#include <stdio.h>', file=f)
        print('#include <stdlib.h>', file=f)
        print('extern void *QEMU_NC_GetHostExecuteCallback();', file=f)
        print('extern void *QEMU_NC_LookUpGuestThunk(const char *);', file=f)
        print('typedef void (*QEMU_NC_HostExecuteCallbackType)(void *, void *, void *[], void *);', file=f)
        print('static QEMU_NC_HostExecuteCallbackType _QEMU_NC_HostExecuteCallback;', file=f)
        for signature, idx in existing_signatures.items():
            cg: CheckGuardData = check_guards[idx]
            print(f'static void *{cg.name}_Thunk;', file=f)
            print(f'static const char {cg.name}_Signature[]=\"{signature}\";', file=f)
        print(f'void X64NC_CONSTRUCTOR __QEMU_NC_Initialize()', file=f)
        print('{', file=f)
        print('    _QEMU_NC_HostExecuteCallback = (QEMU_NC_HostExecuteCallbackType) QEMU_NC_GetHostExecuteCallback();', file=f)
        for _, idx in existing_signatures.items():
            cg: CheckGuardData = check_guards[idx]
            print(f'    if (!({cg.name}_Thunk = QEMU_NC_LookUpGuestThunk({cg.name}_Signature)))', file=f)
            print('    {', file=f)
            print(f'        printf(\"Host Library: Failed to get callback thunk of \\\"%s\\\"\", {cg.name}_Signature);', file=f)
            print(f'        abort();', file=f)
            print('    }', file=f)
        print('}\n', file=f)
        for signature, idx in existing_signatures.items():
            cg: CheckGuardData = check_guards[idx]
            return_type_str = cl.to_type_str(cg.type.get_result())
            arg_types:list[Type] = list(cg.type.argument_types())
            arg_list_str = str(', ').join([f"{cl.to_type_str(arg_types[i])} {f'_arg{i + 1}'}" for i in range(0, len(arg_types))])
            
            decl = f"{return_type_str} {cg.name} ({cl.to_type_str(cg.type)} *_callback, {arg_list_str}"
            if cg.type.is_function_variadic():
                decl += ", ...)"
            else:
                decl += ")"
            check_guard_declarations[signature] = decl
            print(decl, file=f)

            print("{", file=f)
            print('    if ((uintptr_t) _callback > (uintptr_t) _QEMU_NC_HostExecuteCallback)', file=f)
            print('    {', file=f)
            args_arrange = ", ".join(f"_arg{i + 1}" for i in range(0, len(arg_types)))
            print(f'        return _callback({args_arrange});', file=f)
            print('    }', file=f)
            args_arrange = ", ".join(f"&_arg{i + 1}" for i in range(0, len(arg_types)))
            print(f'    void *_args[] = {{{args_arrange}}};', file=f)
            if return_type_str != 'void':
                print(f'    {return_type_str} _ret;', file=f)
                print(f'    _QEMU_NC_HostExecuteCallback({cg.name}_Thunk, (void *) _callback, _args, &_ret);', file=f)
                print('    return _ret;', file=f)
            else:
                print(f'    _QEMU_NC_HostExecuteCallback({cg.name}_Thunk, (void *) _callback, _args, NULL);', file=f)
            print('}\n', file=f)
        check_guard_definitions_code = f.getvalue()
    
    # Generate CFI declarations
    with io.StringIO() as f:
        existing_records: set[str] = set()
        for signature, idx in existing_signatures.items():
            cg: CheckGuardData = check_guards[idx]
            decl = check_guard_declarations[signature]
            
            arg_type: Type
            for arg_type in cg.type.argument_types():
                arg_type = cl.primordial_type(arg_type)
                if arg_type.kind == TypeKind.RECORD:
                    canonical_spelling: str = arg_type.get_canonical().spelling
                    if canonical_spelling in existing_records:
                        continue
                    existing_records.add(canonical_spelling)
                    print(f'{canonical_spelling};', file=f)

            print(f'{decl};', file=f)
        check_guard_declarations_code = f.getvalue()
            

    with open(output_file, mode='w') as f:
        f.writelines(check_guard_declarations_code)
        f.write('\n\n')
        f.writelines(source_code)
        f.write('\n\n')
        f.writelines(check_guard_definitions_code)


if __name__ == '__main__':
    main()