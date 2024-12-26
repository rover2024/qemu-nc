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
from clang.cindex import TranslationUnit


class StringLiteral:
    extern_c = "extern \"C\""
    attribute_constructor = "__attribute__((constructor))"
    attribute_visible = "__attribute__((visibility(\"default\")))"


"""
Walk through the given type and collect all emerged types.
"""
def scan_types(type: Type, visited_types: list[Type], visited_type_spellings: set[str], scan_fields: bool = True):
    type = type.get_canonical()
    if type.spelling in visited_type_spellings:
        return
    visited_types.append(type)
    visited_type_spellings.add(type.spelling)

    if type.kind == TypeKind.POINTER:
        # Pointer type
        scan_types(type.get_pointee(), visited_types, visited_type_spellings)
    elif Typing.is_array(type):
        # Array type, convert to pointer
        scan_types(type.element_type, visited_types, visited_type_spellings)
    elif type.kind == TypeKind.FUNCTIONPROTO:
        # Function pointer type, scan return type and argument types
        scan_types(type.get_result(), visited_types, visited_type_spellings)
        for arg in type.argument_types():
            scan_types(arg, visited_types, visited_type_spellings)
    elif type.kind == TypeKind.FUNCTIONNOPROTO:
        scan_types(type.get_result(), visited_types, visited_type_spellings)
    elif type.kind == TypeKind.RECORD:
            # Struct/Union type, scan members
        if scan_fields:
            for field in type.get_fields():
                scan_types(field.type, visited_types, visited_type_spellings)


"""
Returns if a cursor is a statement block with a trailing semicolon.
"""
def is_statement_block(c: Cursor) -> bool:
    kind: CursorKind = c.kind
    if kind.is_statement():
        return True
    return False
    # extent: SourceRange = c.extent
    # end: SourceLocation = extent.end
    # if not end.file:
    #     return False

    # tu: TranslationUnit = c.translation_unit
    # tokens = list(tu.get_tokens(None, SourceRange.from_locations(end, end)))

    # if len(tokens) == 0:
    #     return False
    # return tokens[0].spelling == ';'


"""
Walk through the given cursor and print in tree structure.
"""
def traverse_cursor(c: Cursor, indent: int):
    range: SourceRange = c.extent
    start: SourceLocation = range.start
    end: SourceLocation = range.end
    referenced: str = c.referenced.spelling if c.referenced else ""
    print(f"{' ' * indent}{c.kind}, \"{c.spelling}\", {c.type.kind}, {start.line}:{start.column}, {end.line}:{end.column}, [{referenced}], is_statment={is_statement_block(c)}")
    
    if indent == -1:
        traverse_cursor(list(c.get_children())[0], 4)
    else:
        for child in c.get_children():
            traverse_cursor(child, indent + 4)


class Typing:
    @staticmethod
    def is_array(type: Type) -> bool:
        return type.kind in [TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY, TypeKind.VARIABLEARRAY]


    @staticmethod
    def is_func_ptr(type: Type) -> bool:
        return Typing.primitive(type).kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]


    """
    Returns the original type without any encapsulation(such as pointer, array, etc).
    """
    @staticmethod
    def primitive(type: Type) -> Type:
        while True:
            type = type.get_canonical()
            if type.kind == TypeKind.POINTER:
                type = type.get_pointee()
                continue
            if Typing.is_array(type):
                type = type.element_type
                continue
            break
        return type


class TypeSpelling:
    """
    Removes 'const' and 'volatile' in spelling.
    """
    @staticmethod
    def remove_cv(s: str) -> str:
        s = s.replace('const ', '')
        s = s.replace('volatile ', '')
        return s
    

    """
    Replace built-in types with common spellings.
    """
    @staticmethod
    def normalize_builtin(s: str) -> str:
        s = s.replace('struct __va_list_tag[1]', 'va_list')
        s = s.replace('struct __va_list_tag *', 'va_list')
        return s


    """
    Returns the spelling in the form that can be used to declare a variable.
    """
    @staticmethod
    def decl(type: Type) -> str:
        type = type.get_canonical()
        if type.spelling in ['struct __va_list_tag[1]', 'struct __va_list_tag *']:
            return 'va_list'
        if Typing.is_func_ptr(type):
            type_str = f'__typeof__({type.spelling})/*FP*/'
        elif Typing.is_array(type):
            type_str = f'__typeof__({type.spelling})/*ARR*/'
            # type_str = TypeSpelling.decl(type.element_type)
            # type_str += '*' if type_str[-1] == '*' else ' *'
        else:
            type_str = type.spelling
        return type_str


    """
    Returns the decayed spelling of a type.
    """
    @staticmethod
    def reduced(type: Type) -> str:
        type = type.get_canonical()
        if type.kind in [ TypeKind.CHAR_U, TypeKind.UCHAR, TypeKind.CHAR_S, TypeKind.SCHAR ]:
            return 'char'
        if type.kind in [ TypeKind.USHORT, TypeKind.SHORT ]:
            return 'short'
        elif type.kind in [ TypeKind.INT, TypeKind.UINT, TypeKind.ENUM ]:
            return 'int'
        elif type.kind in [ TypeKind.LONG, TypeKind.LONGLONG, TypeKind.ULONG, TypeKind.ULONGLONG ]:
            return 'long'
        elif type.kind in [ TypeKind.POINTER, TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO ] or Typing.is_array(type):
            return 'void *'
            # return 'long'
        return TypeSpelling.remove_cv(type.spelling)
    

    """
    Returns the spelling of a call expression.
    """
    @staticmethod
    def call_expr(c: Cursor, result_type: Type, reduce: bool = True) -> str:
        res = TypeSpelling.reduced(result_type) if reduce else TypeSpelling.decl(result_type)
        if res[-1] != '*':
            res += ' '
        res += '('
        res += ', '.join([(TypeSpelling.reduced(arg.type) \
                                if reduce else arg.type.get_canonical().spelling) \
                                    for arg in c.get_arguments()])
        res += ')'
        return TypeSpelling.remove_cv(res) if reduce else res


    """
    Returns the spelling of a fucntion proto type.
    """
    @staticmethod
    def func_type(type: Type, reduce: bool = True) -> str:
        res = TypeSpelling.reduced(type.get_result()) if reduce else TypeSpelling.decl(type.get_result())
        if res[-1] != '*':
            res += ' '
        res += '('
        if type.kind == TypeKind.FUNCTIONPROTO:
            res += ', '.join([(TypeSpelling.reduced(arg_type) \
                                if reduce else arg_type.get_canonical().spelling) \
                                    for arg_type in type.argument_types() ])
            if type.is_function_variadic():
                res += ', ...'
        res += ')'
        return TypeSpelling.remove_cv(res) if reduce else res


class CommandLine:
    @staticmethod
    def flag_values(cmds: list[str], flag: str) -> list[str]:
        res:list[str] = []
        i = 0
        while i < len(cmds):
            if cmds[i] == flag:
                if i + 1 < len(cmds):
                    res.append(cmds[i + 1])
                    i += 2
                    continue
            elif cmds[i].startswith(flag):
                res.append(cmds[i][2:])
                i += 1
                continue
            i += 1
        return res

    @staticmethod
    def include_dirs(cmds: list[str]) -> list[str]:
        return CommandLine.flag_values(cmds, '-I')

    def defnitions(cmds: list[str]) -> list[str]:
        return CommandLine.flag_values(cmds, '-D')