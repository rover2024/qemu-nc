# Usage: python cfiadd.py <source file> [-c <callbacks file>] [-o output] [-X <clang args>]

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
    resource_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'delegen_resources')
    ignored_function_scopes: list[str] = [
        "bsearch"
    ]


class CheckGuardData:
    def __init__(self):
        self.name: str
        self.result_type: Type
        self.arg_types: list[Type]
        self.reduced_spelling: str
        self.canonical_spelling: str
        self.type: Type
        self.no_proto_with_args: bool
    
    def decl(self) -> str:
        return_type_str = cl.TypeSpelling.decl(self.result_type)
        arg_list_str = str(', ').join([f"{cl.TypeSpelling.decl(self.arg_types[i])} {f'_arg{i + 1}'}" for i in range(0, len(self.arg_types))])
        
        decl_str = f"{return_type_str} {self.name} (__typeof__({self.canonical_spelling if self.no_proto_with_args else self.type.get_canonical().spelling}) *_callback"
        if len(self.arg_types) > 0:
            decl_str += f', {arg_list_str}'
        if not self.no_proto_with_args and self.type.kind == TypeKind.FUNCTIONPROTO and self.type.is_function_variadic():
            decl_str += ", ...)"
        else:
            decl_str += ")"
        return cl.TypeSpelling.normalize_builtin(decl_str)


def clang_reveal_call_expr(c: Cursor) -> tuple[Optional[Cursor], Type]:
    # input is CALL_EXPR
    nested_level = 0
    while True:
        if c.kind in [CursorKind.CALL_EXPR]:
            # extract
            c = list(c.get_children())[0]
            nested_level += 1
            continue
        elif c.kind in [CursorKind.BINARY_OPERATOR, CursorKind.CONDITIONAL_OPERATOR, CursorKind.PAREN_EXPR]:
            break
        elif c.kind in [CursorKind.UNEXPOSED_EXPR]:
            children = list(c.get_children())
            if len(children) == 0:
                # Maybe undefined symbol or special symbol(for example `_mm_getcsr`, I don't know why)
                return c, c.type.get_canonical()
            c = children[0]
            continue
        elif c.kind in [CursorKind.MEMBER_REF_EXPR, CursorKind.DECL_REF_EXPR]:
            # get reference
            c = c.referenced
            break
        elif c.kind in [CursorKind.ARRAY_SUBSCRIPT_EXPR, CursorKind.CSTYLE_CAST_EXPR]:
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
    parser.add_argument('-X', nargs=argparse.REMAINDER, metavar="<clang args>", default=[], help='Extra arguments to pass to Clang.')
    parser.add_argument('-c', type=str, metavar="<file>", required=False, help='File contains list of callbacks.')
    parser.add_argument('-o', type=str, metavar="<out>", required=False, help='Output file name')
    parser.add_argument('source_file', type=str, help='Source file to process.')
    args = parser.parse_args()

    # Set the path to the clang library
    cl.setup()

    # Arguments
    callbacks_file: str = args.c if args.c else ''
    source_file: str = args.source_file
    output_file: str = args.o if args.o else source_file

    # Configure the index to parse the header files
    index = Index.create()
    translation_unit = index.parse(source_file, args=['-x', 'c'] + args.X)
    
    # Collect function pointer positions
    target_cursors: list[Cursor] = []
    target_cursor_last_statements: list[Cursor] = []

    function_decls: list[Cursor] = []
    def walkthrough_ast(c: Cursor, stmt: Cursor, parent: Optional[Cursor]):
        if c.extent.start.file and not os.path.samefile(str(c.extent.start.file), source_file):
            return
        skip_children = False
        # if c.kind.is_statement():
        #     stmt = c
        # elif c.kind.is_expression():
        #     if parent and parent.kind == CursorKind.COMPOUND_STMT:
        #         stmt = c
        if c.kind == CursorKind.FUNCTION_DECL:
            stmt = c
        if c.kind == CursorKind.CALL_EXPR:
            target_cursors.append(c)
            target_cursor_last_statements.append(stmt)
        elif c.kind == CursorKind.FUNCTION_DECL:
            function_decls.append(c)
            if c.spelling in Global.ignored_function_scopes:
                skip_children = True
        if not skip_children:
            for child in c.get_children():
                walkthrough_ast(child, stmt, c)
    walkthrough_ast(translation_unit.cursor, translation_unit.cursor, None)

    def contains_source_range(parent: SourceRange, child: SourceRange, accept_equal: bool = True):
        if accept_equal:
            return (parent.start.line < child.start.line or (parent.start.line == child.start.line and parent.start.column <= child.start.column)) \
                    and \
               (parent.end.line > child.end.line or (parent.end.line == child.end.line and parent.end.column >= child.end.column))
        else:
            return (parent.start.line < child.start.line or (parent.start.line == child.start.line and parent.start.column < child.start.column)) \
                    and \
               (parent.end.line > child.end.line or (parent.end.line == child.end.line and parent.end.column > child.end.column))
    

    sorted_target_cursors: list[Cursor] = []
    sorted_target_cursors_is_statement: list[bool] = []
    last_statment: Optional[Cursor] = None
    for i in range(0, len(target_cursors)):
        c = target_cursors[i]
        stmt = target_cursor_last_statements[i]
        # r: SourceRange = c.extent
        # start: SourceLocation = r.start
        # end: SourceLocation = r.end
        # print(f"{c.kind}, \"{c.spelling}\", {c.type.kind}, {start.line}:{start.column}, {end.line}:{end.column}")
        
        if not last_statment or not contains_source_range(last_statment.extent, c.extent) or contains_source_range(last_statment.extent, stmt.extent, False):
            last_statment = stmt
            sorted_target_cursors.append(last_statment)
            sorted_target_cursors_is_statement.append(True)

            # r: SourceRange = stmt.extent
            # start: SourceLocation = r.start
            # end: SourceLocation = r.end
            # print(f"ADD {start.line}:{start.column}, {end.line}:{end.column}")
        sorted_target_cursors.append(c)
        sorted_target_cursors_is_statement.append(False)

    # cl.traverse_cursor(translation_unit.cursor, 0)
    # if 1 + 1 == 2:
    #     return

    with open(source_file, mode='r') as f:
        source_code = f.readlines()
    source_code_copy = source_code.copy()

    # Load callbacks
    callbacks_set: set[str] = set()
    if len(callbacks_file) > 0:
        callbacks_set = read_list_file_as_set(callbacks_file)

    # Range replacing helpers
    def get_source_range(range: SourceRange) -> str:
        start: SourceLocation = range.start
        end: SourceLocation = range.end
        cur_line = start.line - 1
        cur_column = start.column - 1
        res = ''
        while(cur_line < end.line - 1):
            res += source_code_copy[cur_line][cur_column:] + ' '
            cur_line += 1
            cur_column = 0
        res += source_code_copy[cur_line][cur_column:end.column - 1]
        return res
    
    def replace_source_range(range: SourceRange, s: str):
        replace_source(range.start.line, range.start.column, range.end.line, range.end.column, s)
    
    def replace_source(start_line: int, start_column: int, end_line: int, end_column: int, s: str):
        cur_line = start_line - 1
        
        cur_column = start_column - 1
        while(cur_line < end_line - 1):
            source_code[cur_line] = source_code[cur_line][:cur_column]
            cur_line += 1
            cur_column = 0
        source_code[cur_line] = source_code[cur_line][0:cur_column] + s + source_code[cur_line][end_column - 1:]

    # Process source code
    check_guards: list[CheckGuardData] = []
    check_guard_map: dict[str, int] = {}     # signature -> index in `check_guards`
    forward_decl_stack: list[str] = []
    for i in range(0, len(sorted_target_cursors)):
        idx = len(sorted_target_cursors) - 1 - i
        c:Cursor = sorted_target_cursors[idx]
        if sorted_target_cursors_is_statement[idx]:
            if len(forward_decl_stack) > 0:
                replace_source(c.extent.start.line, c.extent.start.column, c.extent.start.line, c.extent.start.column, '\n'.join(forward_decl_stack) + '\n')
            forward_decl_stack.clear()
            continue

        # call expr
        reveal_result = clang_reveal_call_expr(list(c.get_children())[0])
        cursor: Optional[Cursor] = reveal_result[0]
        type: Type = reveal_result[1]

        # print(f'[{i + 1}]')
        # cl.traverse_cursor(c, -1)
        # print(" ")
        # print(f"{cursor.kind if cursor else ''}, {type.kind}")

        if cursor and cursor.kind == CursorKind.FUNCTION_DECL:
            continue
        if type.kind == TypeKind.POINTER:
            type = type.get_pointee()
        if not type.kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]:
            continue
        type = type.get_canonical()

        reduced_spelling:str
        call_args: list[Cursor] = list(c.get_arguments())

        # True if this expression calls a non-prototype function with arguments,
        # which is deprecated in mordern C
        no_proto_with_args = type.kind == TypeKind.FUNCTIONNOPROTO and len(call_args) > 0
        if no_proto_with_args:
            reduced_spelling = cl.TypeSpelling.call_expr(c, type.get_result(), True)
            canonical_spelling = cl.TypeSpelling.call_expr(c, type.get_result(), False)
        else:
            reduced_spelling = cl.TypeSpelling.func_type(type, True)
            canonical_spelling = cl.TypeSpelling.func_type(type, False)
        
        if len(callbacks_set) > 0 and not reduced_spelling in callbacks_set:
            continue

        children:list[Cursor] = list(c.get_children())
        if not children or len(children) == 0:
            continue
        func_ptr = children[0]

        # Prepend first argument
        loc: SourceLocation
        if len(children) > 1:
            loc = children[1].extent.start
            start_line = loc.line
            start_column = loc.column
        else:
            loc = c.extent.end
            start_line = loc.line
            start_column = loc.column - 1
        line = source_code[start_line - 1]
        line = line[:start_column - 1] + get_source_range(func_ptr.extent) + \
             (', ' if len(children) > 1 else '') + line[start_column - 1:]
        source_code[start_line - 1] = line

        # Replace callee
        if canonical_spelling in check_guard_map:
            name = check_guards[check_guard_map[canonical_spelling]].name
        else:
            name = f'__X64NC_CHECK_GUARD_{len(check_guard_map) + 1}'
            check_guard_map[canonical_spelling] = len(check_guards)
        replace_source_range(func_ptr.extent, name)

        cg = CheckGuardData()
        cg.name = name
        cg.result_type = type.get_result()
        if no_proto_with_args:
            cg.arg_types = [arg.type for arg in call_args]
        else:
            cg.arg_types = list(type.argument_types()) if type.kind == TypeKind.FUNCTIONPROTO else []
        cg.reduced_spelling = reduced_spelling
        cg.canonical_spelling = canonical_spelling
        cg.type = type
        cg.no_proto_with_args = no_proto_with_args
        check_guards.append(cg)
        forward_decl_stack.insert(0, f'static {cg.decl()};')

    # Generate CFI definitions
    check_guard_declarations: dict[str, str] = {}
    with io.StringIO() as f:
        print('/****************************************************************************', file=f)
        print(f'** Lifted code from reading C++ file \'{os.path.split(source_file)[-1]}\'', file=f)
        print('**', file=f)
        print('** Created by: QEMU-NC CFI-Lifting tool', file=f)
        print('**', file=f)
        print('** WARNING! All changes made in this file will be lost!', file=f)
        print('*****************************************************************************/', file=f)
        print('extern int printf (const char *, ...);', file=f)
        print('extern void abort (void);', file=f)
        print('#ifndef NULL\n#define NULL ((void*)0)\n#endif', file=f)
        print('\n', file=f)
        print('extern void *x64nc_GetFPExecuteCallback();', file=f)
        print('extern void *x64nc_LookUpCallbackThunk(const char *);', file=f)
        print('typedef void (*X64NC_FP_ExecuteCallback)(void *, void *, void *[], void *);', file=f)
        print('static X64NC_FP_ExecuteCallback _X64NC_HostExecuteCallback;', file=f)
        for _, idx in check_guard_map.items():
            cg: CheckGuardData = check_guards[idx]
            print(f'static void *{cg.name}_Thunk;', file=f)
            print(f'static const char {cg.name}_Signature[]=\"{cl.TypeSpelling.remove_cv(cg.reduced_spelling)}\";', file=f)
        print(f'static void {cl.StringLiteral.attribute_constructor} __X64NC_Initialize()', file=f)
        print('{', file=f)
        print('    _X64NC_HostExecuteCallback = (X64NC_FP_ExecuteCallback) x64nc_GetFPExecuteCallback();', file=f)
        for _, idx in check_guard_map.items():
            cg: CheckGuardData = check_guards[idx]
            print(f'    if (!({cg.name}_Thunk = x64nc_LookUpCallbackThunk({cg.name}_Signature)))', file=f)
            print('    {', file=f)
            print(f'        printf(\"Host Library: Failed to get callback thunk of \\\"%s\\\"\\n\", {cg.name}_Signature);', file=f)
            print(f'        abort();', file=f)
            print('    }', file=f)
        print('}\n', file=f)
        for signature, idx in check_guard_map.items():
            cg: CheckGuardData = check_guards[idx]
            return_type_str = cl.TypeSpelling.decl(cg.result_type)
            decl_str = cg.decl()
            check_guard_declarations[signature] = decl_str
            print(f'static {decl_str}', file=f)

            print("{", file=f)
            print('    if ((long) _callback > (long) _X64NC_HostExecuteCallback)', file=f)
            print('    {', file=f)
            args_arrange = ", ".join(f"_arg{i + 1}" for i in range(0, len(cg.arg_types)))
            print(f'        return _callback({args_arrange});', file=f)
            print('    }', file=f)
            args_arrange = ", ".join(f"&_arg{i + 1}" for i in range(0, len(cg.arg_types)))
            print('    {', file = f)
            print(f'    void *_args[] = {{{args_arrange}}};', file=f)
            if return_type_str != 'void':
                print(f'    {return_type_str} _ret;', file=f)
                print(f'    _X64NC_HostExecuteCallback({cg.name}_Thunk, (void *) _callback, _args, &_ret);', file=f)
                print('    return _ret;', file=f)
            else:
                print(f'    _X64NC_HostExecuteCallback({cg.name}_Thunk, (void *) _callback, _args, NULL);', file=f)
            print('    }', file = f)
            print('}\n', file=f)
        check_guard_definitions_code = f.getvalue()

    if len(check_guard_declarations) > 0:
        with open(output_file, mode='w') as f:
            f.writelines(source_code)
            f.write('\n\n')
            f.writelines(check_guard_definitions_code)


if __name__ == '__main__':
    main()