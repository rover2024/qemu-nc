# Usage: python cfiadd.py <source file> [-I<dir>] [-D<FOO=bar>] [-o output]

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

from .util import clang_scan_type


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
        else:
            raise TypeError(f"Unexpected cursor kind: {c.kind}")

    if nested_level == 0:
        return c, c.type.get_canonical()

    type: Type = c.type
    while nested_level > 0:
        type = type.get_canonical()
        type = type.get_result()
        nested_level -= 1

    return None, type.get_canonical()


def main():
    parser = argparse.ArgumentParser(description='Add CFI check guard for function pointers.')
    parser.add_argument('-I', type=str, action='append', metavar="<dir>", default=[], help='Include path for headers.')
    parser.add_argument('-D', type=str, action='append', metavar="<definition>", default=[], help='Macro definitions.')
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
                                   [f'-D{m}' for m in args.D])
    
    # Collect function pointer positions
    function_pointers: list[Cursor] = []
    def scan_func_ptr(c: Cursor):
        if c.kind == CursorKind.CALL_EXPR:
            function_pointers.append(c)
        for child in c.get_children():
            scan_func_ptr(child, function_pointers)
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
    for c in reversed(function_pointers):
        children:list[Cursor] = list(c.get_children())
        if not children or len(children) < 2:
            continue

        reveal_result = clang_reveal_call_expr(c)
        cursor: Optional[Cursor] = reveal_result[0]
        type: Type = reveal_result[1]

        if cursor and cursor.kind == CursorKind.FUNCTION_DECL:
            continue

        if type.kind == TypeKind.POINTER:
            type = type.get_pointee()
        
        if not type.kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]:
            continue

        func_ptr = children[0]
        first_arg = children[1]

        # Prepend first argument
        start: SourceLocation = first_arg.extent.start
        line = source_code[start.line - 1]
        line = line[:start.column - 1] + get_source_range(func_ptr.extent) + ', ' + line[start.column - 1:]
        source_code[start.line - 1] = line

        # Replace callee
        if type.spelling in existing_signatures:
            name = check_guards[existing_signatures[type.spelling]].name
        else:
            name = f'__CHECK_GUARD_{len(existing_signatures) + 1}__'
            existing_signatures[type.spelling] = len(check_guards)
        replace_source_range(func_ptr.extent, name)

        cg = CheckGuardData()
        cg.name = name
        cg.type = type
        cg.extent = func_ptr.extent
        check_guards.append(cg)

    # Generate CFI definitions
    with io.StringIO() as f:
        for idx in existing_signatures:
            cg: CheckGuardData = check_guards[idx]
            
            arg_list = str(', ').join([arg.spelling for arg in cg.type.argument_types()])
            print(f'{cg.type.get_result().spelling} {cg.name} ({arg_list})')
            pass


    with open(output_file, mode='w') as f:
        f.writelines(source_code)



if __name__ == '__main__':
    main()