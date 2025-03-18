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
import csv

from typing import Any



def main():
    parser = argparse.ArgumentParser(description='Generate CSV file')
    parser.add_argument('input_dir', type=str, help='Directory contains statistic result.')
    parser.add_argument('output_file', type=str, help='File of the CSV.')
    args = parser.parse_args()
    
    input_dir: str = args.input_dir
    output_file: str = args.output_file
    
    output_content = [
        [
            'name', 
            'function_cnt', 
            'simple_va_functions',
            'complex_va_functions',
            'simple_fp_functions',
            'complex_fp_functions'
        ]
    ]
    
    for item in os.listdir(input_dir):
        with open(os.path.join(input_dir, item), 'r') as file:
            obj = json.load(file)
            name: str = obj['name']
            files: list[Any] = obj['files']
            
            function_cnt: int = 0
            simple_va_functions: int = 0
            complex_va_functions: int = 0
            simple_fp_functions: int = 0
            complex_fp_functions: int = 0
            
            for file in files:
                function_cnt += file['function_cnt']
                simple_va_functions += len(file['simple_va_functions'])
                complex_va_functions += len(file['complex_va_functions'])
                simple_fp_functions += len(file['simple_fp_functions'])
                complex_fp_functions += len(file['complex_fp_functions'])
                
            output_content.append(
                            [
                                name, 
                                function_cnt, 
                                simple_va_functions,
                                complex_va_functions,
                                simple_fp_functions,
                                complex_fp_functions
                            ]
            )
    
    with open(output_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        
        # 写入数据
        writer.writerows(output_content)
            


if __name__ == '__main__':
    main()