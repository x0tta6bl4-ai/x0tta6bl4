#!/usr/bin/env python3
"""
Index the workspace directory: collect per-extension counts and sizes, and a directory tree up to a configurable depth.
Usage:
  python scripts/index_workspace.py --root /mnt/AC74CC2974CBF3DC --depth 3 --output /mnt/AC74CC2974CBF3DC/workspace_index.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

IGNORED_DIRS = {
    ".git",
    ".Trash-1000",
    ".venv",
    "System Volume Information",
    "__pycache__",
    "node_modules",
}

# Basic extension categories
EXT_CATEGORIES: Dict[str, str] = {
    # code
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".java": "code",
    ".c": "code",
    ".h": "code",
    ".hpp": "code",
    ".go": "code",
    ".rs": "code",
    ".php": "code",
    ".html": "code",
    ".css": "code",
    ".json": "code",
    ".yml": "code",
    ".yaml": "code",
    ".sh": "code",
    ".sql": "code",
    ".rb": "code",
    ".md": "code",
    ".toml": "code",
    ".ini": "code",
    ".cfg": "code",
    ".txt": "code",
    ".jsx": "code",
    ".tsx": "code",
    ".gradle": "code",
    ".xml": "code",
    ".pl": "code",
    ".pm": "code",
    ".swift": "code",
    ".kt": "code",
    ".dart": "code",
    ".lua": "code",
    ".cmake": "code",
    ".make": "code",
    ".mk": "code",
    ".dockerfile": "code",
    ".env": "code",
    ".gitignore": "code",
    # media
    ".jpg": "media",
    ".jpeg": "media",
    ".png": "media",
    ".gif": "media",
    ".bmp": "media",
    ".tif": "media",
    ".tiff": "media",
    ".svg": "media",
    ".webp": "media",
    ".psd": "media",
    ".ico": "media",
    ".mp4": "media",
    ".mov": "media",
    ".avi": "media",
    ".mkv": "media",
    ".webm": "media",
    ".mp3": "media",
    ".wav": "media",
    ".flac": "media",
    ".aac": "media",
    ".ogg": "media",
    ".3gp": "media",
    ".heic": "media",
    # archive
    ".gz": "archive",
    ".zip": "archive",
    ".rar": "archive",
    ".7z": "archive",
    ".tar": "archive",
    ".xz": "archive",
    ".bz2": "archive",
    ".zst": "archive",
    ".lz4": "archive",
    ".tgz": "archive",
    ".jar": "archive",
    # cache/build
    ".pyc": "cache",
    ".so": "cache",
    ".o": "cache",
    ".obj": "cache",
    ".dll": "cache",
    ".class": "cache",
    ".map": "cache",
    ".lock": "cache",
    ".log": "cache",
    ".tmp": "cache",
    ".part": "cache",
    ".swp": "cache",
    # documents
    ".pdf": "doc",
    ".doc": "doc",
    ".docx": "doc",
    ".xls": "doc",
    ".xlsx": "doc",
    ".ppt": "doc",
    ".pptx": "doc",
    ".odt": "doc",
    ".ods": "doc",
    ".odp": "doc",
    ".rtf": "doc",
    # 3D/CAD/graphics
    ".f3d": "cad",
    ".cdr": "cad",
    ".plt": "cad",
    ".dxf": "cad",
    ".dwg": "cad",
    ".max": "cad",
    ".obj": "cad",
    ".stl": "cad",
    ".blend": "cad",
    ".ps": "cad",
}


@dataclass
class DirNode:
    name: str
    path: str
    dirs: List["DirNode"]
    files: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "dirs": [d.to_dict() for d in self.dirs],
            "files": self.files,
        }


def human_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.2f} {u}"
        size /= 1024
    return f"{size:.2f} TB"  # fallback, though loop should have returned


def build_tree(root: str, max_depth: int) -> DirNode:
    root = os.path.abspath(root)

    def walk(current: str, depth: int) -> DirNode:
        try:
            entries = sorted(os.listdir(current))
        except Exception:
            entries = []
        dirs: List[DirNode] = []
        files: List[str] = []
        for e in entries:
            full = os.path.join(current, e)
            if os.path.isdir(full):
                if e in IGNORED_DIRS:
                    continue
                if depth < max_depth:
                    dirs.append(walk(full, depth + 1))
            else:
                files.append(e)
        return DirNode(
            name=os.path.basename(current) or current,
            path=current,
            dirs=dirs,
            files=files,
        )

    return walk(root, 0)


def scan_all(
    root: str, collect_largest: int = 0
) -> Tuple[Dict[str, Dict[str, int]], int, int, List[Tuple[str, int]]]:
    stats: Dict[str, Dict[str, int]] = {}
    total_files = 0
    total_bytes = 0
    largest: List[Tuple[str, int]] = []  # (path, size)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        for f in filenames:
            full = os.path.join(dirpath, f)
            ext = os.path.splitext(f)[1].lower() or ""
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            bucket = stats.setdefault(ext, {"count": 0, "bytes": 0})
            bucket["count"] += 1
            bucket["bytes"] += size
            total_files += 1
            total_bytes += size
            if collect_largest:
                # maintain sorted list (size desc) with bounded length
                if len(largest) < collect_largest:
                    largest.append((full, size))
                else:
                    # check if current > min
                    min_index = min(range(len(largest)), key=lambda i: largest[i][1])
                    if size > largest[min_index][1]:
                        largest[min_index] = (full, size)
    if collect_largest:
        largest.sort(key=lambda t: t[1], reverse=True)
    return stats, total_files, total_bytes, largest


def summarize_extension_stats(stats: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ext, data in stats.items():
        cat = EXT_CATEGORIES.get(ext, "unknown" if ext else "unknown")
        rows.append(
            {
                "ext": ext if ext else "(no ext)",
                "count": data["count"],
                "bytes": data["bytes"],
                "human": human_size(data["bytes"]),
                "category": cat,
            }
        )
    rows.sort(key=lambda r: r["bytes"], reverse=True)
    return rows


def aggregate_categories(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    acc: Dict[str, Dict[str, int]] = {}
    for r in rows:
        cat = r["category"]
        d = acc.setdefault(cat, {"count": 0, "bytes": 0})
        d["count"] += r["count"]
        d["bytes"] += r["bytes"]
    out: List[Dict[str, Any]] = []
    for cat, d in acc.items():
        out.append(
            {
                "category": cat,
                "count": d["count"],
                "bytes": d["bytes"],
                "human": human_size(d["bytes"]),
            }
        )
    out.sort(key=lambda r: r["bytes"], reverse=True)
    return out


def detect_previous_diff(
    previous_index_path: str, current_files: List[Tuple[str, int]], threshold_bytes: int
) -> Dict[str, List[Dict[str, Any]]]:
    try:
        with open(previous_index_path, "r", encoding="utf-8") as f:
            prev = json.load(f)
    except Exception:
        return {}
    prev_largest = {
        item["path"]: item["bytes"]
        for item in prev.get("largest_files", [])
        if "path" in item
    }
    curr_map = {p: s for p, s in current_files}
    new_files: List[Dict[str, Any]] = []
    removed_files: List[Dict[str, Any]] = []
    grown_files: List[Dict[str, Any]] = []
    for p, s in curr_map.items():
        if p not in prev_largest:
            if s >= threshold_bytes:
                new_files.append({"path": p, "bytes": s, "human": human_size(s)})
        else:
            prev_size = prev_largest[p]
            if s > prev_size and s - prev_size >= threshold_bytes:
                grown_files.append(
                    {
                        "path": p,
                        "old_bytes": prev_size,
                        "new_bytes": s,
                        "delta_bytes": s - prev_size,
                        "delta_human": human_size(s - prev_size),
                    }
                )
    for p, s in prev_largest.items():
        if p not in curr_map and s >= threshold_bytes:
            removed_files.append({"path": p, "bytes": s, "human": human_size(s)})
    return {
        "new_large_files": new_files,
        "removed_large_files": removed_files,
        "grown_large_files": grown_files,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--depth", type=int, default=3)
    ap.add_argument("--output", default="workspace_index.json")
    ap.add_argument(
        "--largest", type=int, default=500, help="Collect top N largest files"
    )
    ap.add_argument(
        "--previous", default=None, help="Path to previous index for diff detection"
    )
    ap.add_argument(
        "--diff-threshold-mb",
        type=int,
        default=100,
        help="Size or growth threshold in MB for diff reporting",
    )
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    tree = build_tree(root, args.depth)
    ext_stats_raw, total_files, total_bytes, largest_files = scan_all(
        root, args.largest
    )
    ext_stats = summarize_extension_stats(ext_stats_raw)
    categories = aggregate_categories(ext_stats)
    largest_serialized: List[Dict[str, Any]] = [
        {"path": p, "bytes": s, "human": human_size(s)} for p, s in largest_files
    ]
    diff = {}
    if args.previous:
        diff = detect_previous_diff(
            args.previous, largest_files, args.diff_threshold_mb * 1024 * 1024
        )

    payload: Dict[str, Any] = {
        "root": root,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_bytes_human": human_size(total_bytes),
        "top_extensions": ext_stats[:50],
        "extensions_all": ext_stats,
        "categories": categories,
        "tree_depth": args.depth,
        "tree": tree.to_dict(),
        "ignored_dirs": sorted(list(IGNORED_DIRS)),
        "python": sys.version,
        "largest_files": largest_serialized,
        "diff": diff,
        "largest_n": args.largest,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    # Also write separate top-largest file
    top_largest_path = os.path.join(os.path.dirname(args.output), "top-largest.json")
    with open(top_largest_path, "w", encoding="utf-8") as lf:
        json.dump(largest_serialized, lf, ensure_ascii=False, indent=2)
    print(
        f"Index written to {args.output} (files={total_files}, size={human_size(total_bytes)}); largest saved to {top_largest_path}"
    )


if __name__ == "__main__":
    main()
