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

from clang.cindex import Config

from typing import Any, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import python.clang as cl
from python.text import *

class PackageInfo:
    def __init__(self):
        self.name: str = ''
        self.flags: list[str] = []
        self.libs: list[str] = []
        self.headers: list[str] = []


def process_package(pkg: str) -> Optional[PackageInfo]:
    # Get name
    idx = pkg.find('-dev')
    if idx < 0:
        return None
    name = pkg[0:idx]

    flags: list[str] = []
    libs: list[str] = []
    headers: list[str] = []

    # 1. Use `dpkg -L` to search headers
    cmds: list[str] = [ "dpkg", "-L", pkg ]
    result = subprocess.run(
        cmds,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"Running `{' '.join(cmds)}` error:\n {result.stderr}")
        return None
    files = result.stdout.split('\n')
    for file in files:
        if len(file) == 0:
            continue
        if os.path.islink(file):
            file = os.readlink(file)
        if not os.path.exists(file):
            continue

        ext = (''.join(pathlib.Path(file).suffixes)).lower()
        if ext == '.pc':
            cmds: list[str] = [ "pkg-config", '--libs', file, '--cflags' ]
            result = subprocess.run(
                cmds,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"Running `{' '.join(cmds)}` error:\n {result.stderr}")
                continue
            flags += shlex.split(result.stdout)
        elif ext == '.h':
            if file in headers:
                continue
            headers.append(file)
        elif '.so' in ext:
            if file in libs:
                continue
            libs.append(file)
    
    # Check headers
    valid_headers: list[str] = []
    for header in headers:
        cmds: list[str] = [ "gcc", '-x', 'c', header, '-fsyntax-only' ] + flags
        result = subprocess.run(
            cmds,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            # print(f"Running `{' '.join(cmds)}` error:\n {result.stderr}")
            continue
        valid_headers.append(header)
    
    if len(valid_headers) == 0:
        return None
    
    info = PackageInfo()
    info.name = name
    info.flags = flags
    info.libs = libs
    info.headers = valid_headers
    return info


def main():
    parser = argparse.ArgumentParser(description='Collect information of interfaces of the libraries.')
    parser.add_argument('packages_file', type=str, help='File contains list of packages.')
    parser.add_argument('output_file', type=str, help='File of the result.')
    args = parser.parse_args()

    # Required tools
    # llvm-18
    # apt
    # apt-file
    # dpkg
    # pkg-config

    # Args
    packages_file: str = args.packages_file
    output_file: str = args.output_file
    
    # Load names
    packages_set = read_list_file_as_set(packages_file)

    i = 0
    doc = []
    for pkg in packages_set:
        i += 1
        print(f"[{i}/{len(packages_set)}] {pkg}")
        info = process_package(pkg)
        if info is None:
            continue
        obj = {
            'name': info.name,
            'flags': info.flags,
            'libs': info.libs,
            'headers': info.headers
        }
        doc.append(obj)

    jsondata = json.dumps(doc)
    with open(output_file, 'w') as file:
        file.write(jsondata)


if __name__ == '__main__':
    main()