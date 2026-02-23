#!/usr/bin/env python3
import os
import hashlib
from collections import defaultdict

def get_file_hash(filepath):
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except: return None

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
    total_potential = sum(len(p) for p in potential_dupes)
    print(f"Potential candidates by size: {total_potential} files in {len(potential_dupes)} groups.")
    
    duplicates = defaultdict(list)
    for group in potential_dupes:
        for path in group:
            h = get_file_hash(path)
            if h: duplicates[h].append(path)
    
    final_dupes = {h: p for h, p in duplicates.items() if len(p) > 1}
    total_extra = sum(len(p) - 1 for p in final_dupes.values())
    
    with open('duplicates_report.txt', 'w') as f:
        for h, paths in final_dupes.items():
            f.write("Hash: {0}
".format(h))
            for p in paths:
                f.write("  {0}
".format(p))
            f.write("
")
    
    print(f"Analysis complete! Found {len(final_dupes)} unique photo hashes with {total_extra} duplicate files.")
    return final_dupes

if __name__ == "__main__":
    find_duplicates_fast('СЕМЕЙНЫЙ_АРХИВ_ИТОГ')
