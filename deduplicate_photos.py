#!/usr/bin/env python3
import os
import hashlib
from collections import defaultdict

def get_file_hash(filepath):
    """Считает хеш файла порциями."""
    hasher = hashlib.md5()
    try:
        if os.path.islink(filepath): return None
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (IOError, OSError):
        return None

def find_duplicates(root_dir):
    hashes = defaultdict(list)
    print(f"Analyzing files in {root_dir}...")
    
    # Рекурсивный обход
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                path = os.path.join(root, file)
                file_hash = get_file_hash(path)
                if file_hash:
                    hashes[file_hash].append(path)
    
    # Группируем дубликаты
    duplicates = {h: p for h, p in hashes.items() if len(p) > 1}
    total_extra = sum(len(p) - 1 for p in duplicates.values())
    
    print(f"Found {len(duplicates)} groups of duplicates, total extra files: {total_extra}")
    
    # Сохраняем отчет (используем обычный format для совместимости)
    with open('duplicates_report.txt', 'w') as f:
        for h, paths in duplicates.items():
            f.write("Hash: {0}\n".format(h))
            for p in paths:
                f.write("  {0}\n".format(p))
            f.write("\n")
    
    print("Full report saved to 'duplicates_report.txt'.")
    return duplicates

if __name__ == "__main__":
    find_duplicates('СЕМЕЙНЫЙ_АРХИВ_ИТОГ')
