import argparse
import json
import shlex
import sys
import subprocess
import os

def main():
    parser = argparse.ArgumentParser(description='Read compile commands and add CFIs.')
    parser.add_argument('callbacks_file', type=str, help='File contains list of callbacks.')
    parser.add_argument('compile_commands', type=str, help='Compile commands file path.')
    args = parser.parse_args()

    python_executable = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfiadd.py')

    callbacks_file: str = args.callbacks_file
    compile_commands_file: str = args.compile_commands

    with open(compile_commands_file) as f:
        json_doc = list(json.load(f))

    all_count = len(json_doc)
    for i in range(0, all_count):
        obj = json_doc[i]
        dir: str = obj['directory']
        filename: str = obj['file']
        source_file = filename if os.path.isabs(filename) else os.path.join(dir, filename)
        temp_file = f'{source_file}.tmp'
        
        print(f'[{i + 1}/{all_count}] Preprocessing {source_file}')

        tokens = shlex.split(obj['command'])
        cmds: list[str] = [ tokens[0], '-E', '-o', temp_file ]
        
        i = 1
        while i < len(tokens):
            if tokens[i] == '-o':
                i += 2
                continue
            cmds.append(tokens[i])
            i += 1

        # Run CC
        result = subprocess.run(
            cmds,
            capture_output=True,
            text=True
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
        cmds = [ python_executable, script_path, '-c', callbacks_file, temp_file, '-o', source_file ]
        result = subprocess.run(
            cmds,
            capture_output=True,
            text=True
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
        os.remove(temp_file)


if __name__ == '__main__':
    main()