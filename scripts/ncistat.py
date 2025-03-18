import sys
import os
import re
import io
import argparse
import shutil
import json
import subprocess
import shlex
import pathlib
from tqdm import tqdm

from clang.cindex import Config
from clang.cindex import Index
from clang.cindex import Config
from clang.cindex import Index
from clang.cindex import Cursor
from clang.cindex import CursorKind
from clang.cindex import Type
from clang.cindex import TypeKind
from clang.cindex import SourceRange
from clang.cindex import SourceLocation

from typing import Any, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import python.clang as cl
from python.text import *

class Global:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'ncconfig.json')


class FileStat:
    def __init__(self):
        self.file: str = ''
        self.function_cnt: int = 0
        self.simple_va_functions: list[str] = []
        self.complex_va_functions: list[str] = []
        self.simple_fp_functions: list[str] = []
        self.complex_fp_functions: list[str] = []
    
    def to_dict(self):
        return {
            'file': self.file,
            'function_cnt': self.function_cnt,
            'simple_va_functions': self.simple_va_functions,
            'complex_va_functions': self.complex_va_functions,
            'simple_fp_functions': self.simple_fp_functions,
            'complex_fp_functions': self.complex_fp_functions
        }


class LibStat:
    def __init__(self):
        self.name: str = ''
        self.files: list[FileStat] = []
        self.simple_fp_records: list[str] = []
        self.complex_fp_records: list[str] = []
    
    def to_dict(self):
        return {
            'name': self.name,
            'files': [item.to_dict() for item in self.files],
            'simple_fp_records': self.simple_fp_records,
            'complex_fp_records': self.complex_fp_records,
        }

def is_fp_record(type: Type, visited_spellings: set[str], records_map: dict[str, tuple[bool, bool]]) -> tuple[bool, bool]:
    spelling = cl.TypeSpelling.remove_cv(type.get_canonical().spelling)
    if spelling in visited_spellings:
        return False, False
    visited_spellings.add(spelling)
    
    if spelling in records_map:
        return records_map[spelling]
    
    declaration = type.get_declaration()
    type = type.get_canonical()
    if declaration.kind == CursorKind.UNION_DECL:
        for field in type.get_fields():
            sub_type = cl.Typing.primitive(field.type)
            if cl.Typing.is_func_ptr(sub_type):
                records_map[spelling] = True, True
                return True, True
            if sub_type.kind == TypeKind.RECORD:
                is_fp1, _ = is_fp_record(sub_type, visited_spellings, records_map)
                if is_fp1:
                    records_map[spelling] = True, True
                    return True, True
        records_map[spelling] = False, False
        return False, False
    elif declaration.kind == CursorKind.STRUCT_DECL:
        is_fp = False
        for field in type.get_fields():
            field_type: Type = field.type.get_canonical()
            sub_type: Type
            if field_type.kind == TypeKind.POINTER:
                if field_type.get_pointee().get_canonical().kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]:
                    is_fp = True
                    continue
            elif field_type.kind == TypeKind.RECORD:
                is_fp1, is_complex1 = is_fp_record(field_type, visited_spellings, records_map)
                if is_fp1:
                    is_fp = True
                    if is_complex1:
                        records_map[spelling] = True, True
                        return True, True
                continue
            sub_type = cl.Typing.primitive(field_type)
            if sub_type.kind == TypeKind.RECORD:
                is_fp1, _ = is_fp_record(sub_type, visited_spellings, records_map)
                if is_fp1:
                    records_map[spelling] = True, True
                    return True, True
            elif cl.Typing.is_func_ptr(sub_type):
                records_map[spelling] = True, True
                return True, True
        records_map[spelling] = is_fp, False
        return is_fp, False


def is_fp_function(c: Cursor, records_map: dict[str, tuple[bool, bool]]) -> tuple[bool, bool]:
    all_types: list[Type] = []
    all_types.append(c.result_type)
    for arg in c.get_arguments():
        all_types.append(arg.type)
    
    exists = False
    type: Type
    for type in all_types:
        type = type.get_canonical()
        if type.kind == TypeKind.POINTER:
            pointee_type: Type = type.get_pointee().get_canonical()
            if pointee_type.kind in [TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO]:
                exists = True
                continue
            elif pointee_type.kind == TypeKind.RECORD:
                visited_spellings = set()
                exists1, complex = is_fp_record(pointee_type, visited_spellings, records_map)
                if not exists1:
                    continue
                exists = True
                if not complex:
                    continue
                return True, True
        elif type.kind == TypeKind.RECORD:
            visited_spellings = set()
            exists1, complex = is_fp_record(type, visited_spellings, records_map)
            if not exists1:
                continue
            exists = True
            if not complex:
                continue
            return True, True
        sub_type = cl.Typing.primitive(type)
        if sub_type.kind == TypeKind.RECORD:
            visited_spellings = set()
            is_fp1, _ = is_fp_record(sub_type, visited_spellings, records_map)
            if is_fp1:
                return True, True
        elif cl.Typing.is_func_ptr(sub_type):
            return True, True
    return exists, False 


def is_va_function(c: Cursor) -> tuple[bool, bool]:
    type: Type = c.type.get_canonical()
    if type.kind != TypeKind.FUNCTIONPROTO:
        return False, False
    
    if type.is_function_variadic():
        # Get the last argument type
        arg_types: list[Type] = list(type.argument_types())
        if len(arg_types) != 0:
            if arg_types[-1].spelling in ['char *', 'const char *', 'char []']:
                return True, False
        return True, True
    else:
        arg_types: list[Type] = list(type.argument_types())
        if len(arg_types) != 0:
            for i in range(0, len(arg_types)):
                if cl.TypeSpelling.normalize_builtin(arg_types[i].get_canonical().spelling) == 'va_list':
                    if i != len(arg_types) - 1 or i == 0:
                        return True, True
                    else:
                        if arg_types[-2].spelling in ['char *', 'const char *', 'char []']:
                            return True, False
                        return True, True
        return False, False


def main():
    parser = argparse.ArgumentParser(description='Collect information of interfaces of the libraries.')
    parser.add_argument('info_file', type=str, help='File contains list of libraries info.')
    parser.add_argument('output_dir', type=str, help='Directory of the result.')
    args = parser.parse_args()
    
    # Read configuration file
    with open(Global.config_path, 'r') as file:
        json_doc = json.load(file)

        # Set the path to the clang library
        Config.set_library_file(json_doc['libclang'])
        
    # Args
    info_file: str = args.info_file
    output_dir: str = args.output_dir
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Read info file
    with open(info_file) as file:
        info_doc = json.load(file)
    
    i: int = 0
    for info in info_doc:
        name: str = info['name']
        flags: list[str] = info['flags']
        headers: list[str] = info['headers']
        
        print(f"[{i + 1}/{len(info_doc)}] Processing {name}")
        i += 1
        
        output_file = os.path.join(output_dir, f'{name}.json')
        if os.path.exists(output_file):
            print("Exists")
            continue
        
        lib_stat = LibStat()
        lib_stat.name = name
        
        all_function_names: set[str] = set()
        function_names: set[str] = set()
        records_map: dict[str, tuple[bool, bool]] = {}
        
        for header_file in tqdm(headers):
            file_stat = FileStat()
            file_stat.file = header_file
            
            # Configure the index to parse the header files
            index = Index.create()
            # print(header_file)
            try:
                translation_unit = index.parse(header_file, args=['-x', 'c'] + flags)
            except Exception as e:
                print('Exception:', e)
                continue
            
            # Scan
            c: Cursor
            for c in translation_unit.cursor.get_children():
                spelling: str = c.spelling
                if c.kind == CursorKind.FUNCTION_DECL:
                    if c.extent.start.file:
                        if not os.path.samefile(str(c.extent.start.file), header_file):
                            continue
                        
                    if not spelling in function_names:
                        function_names.add(spelling)
                        
                        is_fp, is_fp_complex = is_fp_function(c, records_map)
                        if is_fp:
                            if is_fp_complex:
                                file_stat.complex_fp_functions.append(spelling)
                            else:
                                file_stat.simple_fp_functions.append(spelling)
                        
                        is_va, is_va_complex = is_va_function(c)
                        if is_va:
                            if is_va_complex:
                                file_stat.complex_va_functions.append(spelling)
                            else:
                                file_stat.simple_va_functions.append(spelling)
                        
                        file_stat.function_cnt += 1

            lib_stat.files.append(file_stat)
        
            
        for k, v in records_map.items():
            if v[0]:
                if v[1]:
                    lib_stat.complex_fp_records.append(k)
                else:
                    lib_stat.simple_fp_records.append(k)

        jsondata = json.dumps(lib_stat.to_dict())
        with open(os.path.join(output_file), 'w') as file:
            file.write(jsondata)
    

if __name__ == '__main__':
    main()