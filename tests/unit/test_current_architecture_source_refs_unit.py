from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARCHITECTURE_ROOT = ROOT / "docs" / "architecture"
LINE_REF_RE = re.compile(r"^(?P<path>.+):(?P<line>\d+)$")


def _source_refs(value: Any) -> list[str]:
    refs: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source_refs":
                refs.extend(str(item) for item in child)
            elif key == "source_ref":
                refs.append(str(child))
            else:
                refs.extend(_source_refs(child))
    elif isinstance(value, list):
        for child in value:
            refs.extend(_source_refs(child))
    return refs


def test_current_architecture_line_source_refs_resolve_repo_wide():
    failures: list[str] = []

    for map_path in sorted(ARCHITECTURE_ROOT.glob("CURRENT_*.json")):
        payload = json.loads(map_path.read_text(encoding="utf-8"))
        for source_ref in _source_refs(payload):
            match = LINE_REF_RE.match(source_ref)
            if match is None:
                continue
            source_path = ROOT / match.group("path")
            if not source_path.exists():
                failures.append(f"{map_path.relative_to(ROOT)} -> {source_ref}: missing file")
                continue
            line_count = len(source_path.read_text(encoding="utf-8").splitlines())
            line_number = int(match.group("line"))
            if line_number < 1 or line_number > line_count:
                failures.append(
                    f"{map_path.relative_to(ROOT)} -> {source_ref}: "
                    f"line outside 1..{line_count}"
                )

    assert failures == []
