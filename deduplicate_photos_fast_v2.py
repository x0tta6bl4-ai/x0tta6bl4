#!/usr/bin/env python3
import os
import hashlib
from collections import defaultdict

def find_duplicates_fast(root_dir):
    size_map = defaultdict(list)
    print(f"Scanning sizes in {root_dir}...")
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                path = os.path.join(root, file)
                try:
                    size = os.path.getsize(path)
                    size_map[size].append(path)
                except: continue
    
    potential_dupes = [paths for paths in size_map.values() if len(paths) > 1]
    
    final_dupes = defaultdict(list)
    for group in potential_dupes:
        for path in group:
            hasher = hashlib.md5()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            h = hasher.hexdigest()
            final_dupes[h].append(path)
    
    res = {h: p for h, p in final_dupes.items() if len(p) > 1}
    total_extra = sum(len(p) - 1 for p in res.values())
    
    with open('duplicates_report.txt', 'w') as f:
        for h, paths in res.items():
            f.write("Hash: " + h + "
")
            for p in paths:
                f.write("  " + p + "
")
            f.write("
")
    
    print("Found " + str(total_extra) + " duplicate files.")

if __name__ == "__main__":
    find_duplicates_fast('СЕМЕЙНЫЙ_АРХИВ_ИТОГ')
