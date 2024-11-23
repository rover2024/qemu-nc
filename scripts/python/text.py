from __future__ import annotations

import re

from typing import Optional

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
    
    def replacement(match: re.Match):
        key = match.group(1)  # Extract XXX
        return replacements.get(key, "")
    
    updated_content = re.sub(r'@([\w_]+)@', replacement, content)
    
    if output_file is None:
        output_file = file_path

    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(updated_content)