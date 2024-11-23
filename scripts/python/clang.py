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


def to_type_str(type: Type) -> str:
    if is_function_pointer(type):
        type_str = f'__typeof__({type.get_canonical().spelling})'
    elif type.kind == TypeKind.CONSTANTARRAY:
        type_str = type.element_type.get_canonical().spelling + " *"
    else:
        type_str = type.get_canonical().spelling
    return type_str