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

def read_list_file_as_set(filename: str) -> set[str]:
    with open(filename) as file:
        symbols = [line.strip() for line in file if line.strip()]
    symbols_set: set[str] = set()
    for symbol in symbols:
        symbols_set.add(symbol)
    return symbols_set


def replace_file_placeholders(file_path: str, replacements: dict[str, str], output_file: Optional[str] = None):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    def replacement(match):
        key = match.group(1)  # 提取 XXX
        return replacements.get(key, "")
    
    updated_content = re.sub(r'@([\w_]+)@', replacement, content)
    
    if output_file is None:
        output_file = file_path

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(updated_content)


def clang_scan_type(type: Type, visited_types: list[Type], visited_type_spellings: set[str]):
    canonical_type: Type = type.get_canonical()
    if canonical_type.spelling in visited_type_spellings:
        return
    visited_types.append(canonical_type)
    visited_type_spellings.add(canonical_type.spelling)

    if canonical_type.kind == TypeKind.POINTER:
        # Pointer type
        clang_scan_type(canonical_type.get_pointee(), visited_types, visited_type_spellings)

    elif canonical_type.kind == TypeKind.RECORD:
        # Struct type, scan members
        for field in canonical_type.get_declaration().get_children():
            if field.kind == CursorKind.FIELD_DECL:
                clang_scan_type(field.type, visited_types, visited_type_spellings)
    
    elif canonical_type.kind == TypeKind.CONSTANTARRAY:
        # Const array type, convert to pointer
        element_type = canonical_type.element_type
        clang_scan_type(element_type, visited_types, visited_type_spellings)
    
    elif canonical_type.kind == TypeKind.FUNCTIONPROTO:
        # Function pointer type, scan return type and argument types
        clang_scan_type(canonical_type.get_result(), visited_types, visited_type_spellings)
        for arg in canonical_type.argument_types():
            clang_scan_type(arg, visited_types, visited_type_spellings)


def clang_traverse_cursor(c: Cursor, indent: int):
    range: SourceRange = c.extent
    start: SourceLocation = range.start
    end: SourceLocation = range.end
    referenced: str = c.referenced.spelling if c.referenced else ""
    print(f"{' ' * indent}{c.kind}, \"{c.spelling}\", {start.line}:{start.column}, {end.line}:{end.column}, [{referenced}]")
    
    if indent == 0:
        clang_traverse_cursor(list(c.get_children())[0], indent + 4)
    else:
        for child in c.get_children():
            clang_traverse_cursor(child, indent + 4)


def is_function_pointer(type: Type) -> bool:
    canonical_type: Type = type.get_canonical()
    if canonical_type.kind == TypeKind.POINTER:
        return is_function_pointer(canonical_type.get_pointee())
    elif canonical_type.kind == TypeKind.CONSTANTARRAY:
        return is_function_pointer(canonical_type.element_type)
    return canonical_type.kind == TypeKind.FUNCTIONPROTO or canonical_type.kind == TypeKind.FUNCTIONNOPROTO