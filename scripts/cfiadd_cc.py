from __future__ import annotations;

import argparse
import json
import shlex
import sys
import subprocess
import os
import re

# test_files: list[str] = [
#     "driver/others/blas_server.c",
#     "lapack-netlib/SRC/cgees.c",
#     "lapack-netlib/SRC/cgeesx.c",
#     "lapack-netlib/SRC/cgges.c",
#     "lapack-netlib/SRC/cgges3.c",
#     "lapack-netlib/SRC/cggesx.c",
#     "lapack-netlib/SRC/dgees.c",
#     "lapack-netlib/SRC/dgeesx.c",
#     "lapack-netlib/SRC/dgges.c",
#     "lapack-netlib/SRC/dgges3.c",
#     "lapack-netlib/SRC/dggesx.c",
#     "lapack-netlib/SRC/sgees.c",
#     "lapack-netlib/SRC/sgeesx.c",
#     "lapack-netlib/SRC/sgges.c",
#     "lapack-netlib/SRC/sgges3.c",
#     "lapack-netlib/SRC/sggesx.c",
#     "lapack-netlib/SRC/zgees.c",
#     "lapack-netlib/SRC/zgeesx.c",
#     "lapack-netlib/SRC/zgges.c",
#     "lapack-netlib/SRC/zgges3.c",
#     "lapack-netlib/SRC/zggesx.c",
#     "utest/utest_main.c"
# ]

def main():
    parser = argparse.ArgumentParser(description='Read compile commands and add CFIs.')
    parser.add_argument('callbacks_file', type=str, help='File contains list of callbacks.')
    parser.add_argument('compile_commands', type=str, help='Compile commands file path.')
    parser.add_argument('-E', action='store_true', help='Run `gcc -E` first')
    args = parser.parse_args()

    python_executable = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfiadd.py')

    callbacks_file: str = args.callbacks_file
    compile_commands_file: str = args.compile_commands
    expand: bool = True if args.E else False

    callbacks_file = callbacks_file if os.path.isabs(callbacks_file) else os.path.join(os.getcwd(), callbacks_file)

    with open(compile_commands_file) as f:
        json_doc = list(json.load(f))

    all_count = len(json_doc)
    for i in range(0, all_count):
        obj = json_doc[i]
        dir: str = obj['directory']
        filename: str = obj['file']
        
        # is_test_file = False
        # for item in test_files:
        #     if filename.endswith(item):
        #         is_test_file = True
        #         break
        # if not is_test_file:
        #     continue

        source_file = filename if os.path.isabs(filename) else os.path.join(dir, filename)
        temp_file = f'{source_file}.tmp'
        
        print(f'[{i + 1}/{all_count}] Preprocessing {source_file}')

        tokens = obj['arguments'] if 'arguments' in obj else shlex.split(obj['command'])
        # for i in range(len(tokens)):
        #     tokens[i] = tokens[i].replace('../..', os.path.dirname(os.path.dirname(dir)))
        #     tokens[i] = tokens[i].replace('..', os.path.dirname(dir))
        #     tokens[i] = tokens[i].replace('-I.', '-I' + dir)

        i = 1
        compile_options: list[str] = []
        while i < len(tokens):
            if tokens[i] == '-o':
                i += 2
                continue
            if tokens[i] == '-c':
                i += 2
                continue
            compile_options.append(tokens[i])
            i += 1

        if expand:
            # Run CC
            cmds: list[str] = [ tokens[0], '-E', source_file, '-o', temp_file ] + compile_options
            result = subprocess.run(
                cmds,
                capture_output=True,
                text=True,
                cwd=dir
            )
            print(' '.join(cmds))
            print(f'Exit code: {result.returncode}')
            if result.returncode != 0:
                print('--------------------------------------------------------------------')
                print('[STDOUT]')
                print(result.stdout)
                print('[STDERR]')
                print(result.stderr)
                print('--------------------------------------------------------------------')
                exit(-1)
            
        # Run CFI-ADD
        cmds = [ python_executable, script_path, '-c', callbacks_file ]
        if expand:
            cmds += [ temp_file, '-o', source_file ]
        else:
            cmds += [ source_file, '-o', source_file, '-X' ] + compile_options
        result = subprocess.run(
            cmds,
            capture_output=True,
            text=True,
            cwd=dir
        )
        print(' '.join(cmds))
        print(f'Exit code: {result.returncode}')
        print('--------------------------------------------------------------------')
        print('[STDOUT]')
        print(result.stdout)
        print('[STDERR]')
        print(result.stderr)
        print('--------------------------------------------------------------------')
        if result.returncode != 0:
            exit(-1)
        
        if expand:
            os.remove(temp_file)


if __name__ == '__main__':
    main()