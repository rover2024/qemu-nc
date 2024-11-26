from __future__ import annotations

import re

from clang.cindex import Config
from clang.cindex import Index
from clang.cindex import Cursor
from clang.cindex import CursorKind
from clang.cindex import Type
from clang.cindex import TypeKind
from clang.cindex import SourceRange
from clang.cindex import SourceLocation

class StringLiteral:
    extern_c: str = "extern \"C\""
    attribute_constructor = "__attribute__((constructor))"
    attribute_visible = "__attribute__((visibility(\"default\")))"

def scan_type(type: Type, visited_types: list[Type], visited_type_spellings: set[str]):
    canonical_type: Type = type.get_canonical()
    if canonical_type.spelling in visited_type_spellings:
        return
    visited_types.append(canonical_type)
    visited_type_spellings.add(canonical_type.spelling)

    if canonical_type.kind == TypeKind.POINTER:
        # Pointer type
        scan_type(canonical_type.get_pointee(), visited_types, visited_type_spellings)

    elif canonical_type.kind == TypeKind.RECORD:
        # Struct type, scan members
        for field in canonical_type.get_declaration().get_children():
            if field.kind == CursorKind.FIELD_DECL:
                scan_type(field.type, visited_types, visited_type_spellings)
    
    elif canonical_type.kind == TypeKind.CONSTANTARRAY:
        # Const array type, convert to pointer
        element_type = canonical_type.element_type
        scan_type(element_type, visited_types, visited_type_spellings)
    
    elif canonical_type.kind == TypeKind.FUNCTIONPROTO:
        # Function pointer type, scan return type and argument types
        scan_type(canonical_type.get_result(), visited_types, visited_type_spellings)
        for arg in canonical_type.argument_types():
            scan_type(arg, visited_types, visited_type_spellings)


def traverse_cursor(c: Cursor, indent: int):
    range: SourceRange = c.extent
    start: SourceLocation = range.start
    end: SourceLocation = range.end
    referenced: str = c.referenced.spelling if c.referenced else ""
    print(f"{' ' * indent}{c.kind}, \"{c.spelling}\", {start.line}:{start.column}, {end.line}:{end.column}, [{referenced}]")
    
    if indent == 0:
        traverse_cursor(list(c.get_children())[0], indent + 4)
    else:
        for child in c.get_children():
            traverse_cursor(child, indent + 4)


def is_function_pointer(type: Type) -> bool:
    return primordial_type(type).kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]


def primordial_type(type: Type) -> Type:
    while True:
        type = type.get_canonical()
        if type.kind == TypeKind.POINTER:
            type = type.get_pointee()
            continue
        if type.kind == TypeKind.CONSTANTARRAY:
            type = type.element_type
            continue
        break
    return type


class types:
    @staticmethod
    def reduced(type: Type) -> str:
        type = type.get_canonical()
        if type.kind in [ TypeKind.CHAR_U, TypeKind.UCHAR, TypeKind.CHAR_S, TypeKind.SCHAR]:
            return 'char'
        elif type.kind in [ TypeKind.INT, TypeKind.UINT ]:
            return 'int'
        elif type.kind in [ TypeKind.LONG, TypeKind.LONGLONG, TypeKind.ULONG, TypeKind.ULONGLONG]:
            return 'long'
        elif type.kind in [ TypeKind.POINTER, TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO, TypeKind.CONSTANTARRAY ]:
            return 'void *'
            # return 'long'
        return types.remove_cv(type.spelling)
    
    @staticmethod
    def remove_cv(s: str) -> str:
        s = s.replace('const ', '')
        s = s.replace('volatile ', '')
        return s

    @staticmethod
    def to_str(type: Type) -> str:
        type = type.get_canonical()
        if is_function_pointer(type):
            type_str = f'__typeof__({type.spelling})/*FP*/'
        elif type.kind == TypeKind.CONSTANTARRAY:
            type_str = types.to_str(type.element_type)
            type_str += '*' if type_str[-1] == '*' else ' *'
        else:
            type_str = type.spelling
        return type_str
    
    @staticmethod
    def call_expr_to_str(c: Cursor, result_type: Type, reduce: bool = True) -> str:
        """Returns the simplest spelling of a call expression."""
        res = types.reduced(result_type) if reduce else types.to_str(result_type)
        if res[-1] != '*':
            res += ' '
        res += '('
        res += ', '.join([(types.reduced(arg.type) \
                                if reduce else arg.type.get_canonical().spelling) \
                                    for arg in c.get_arguments()])
        res += ')'
        return types.remove_cv(res) if reduce else res


    @staticmethod
    def func_type_to_str(type: Type, reduce: bool = True) -> str:
        """Returns the simplest spelling of a fucntion proto type."""
        res = types.reduced(type.get_result()) \
            if reduce else types.reduced(type.get_result())
        if res[-1] != '*':
            res += ' '
        res += '('
        if type.kind == TypeKind.FUNCTIONPROTO:
            res += ', '.join([(types.reduced(arg_type) \
                                if reduce else arg_type.get_canonical().spelling) \
                                    for arg_type in type.argument_types() ])
            if type.is_function_variadic():
                res += ', ...'
        res += ')'
        return types.remove_cv(res) if reduce else res