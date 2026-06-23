"""Inventory guard for API readiness claim gates."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_all_api_readiness_status_helpers_include_cross_plane_claim_gate():
    missing: list[str] = []
    for path in sorted((ROOT / "src/api").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.endswith("readiness_status"):
                continue
            segment = ast.get_source_segment(source, node) or ""
            if "cross_plane_claim_gate" not in segment:
                missing.append(f"{path.relative_to(ROOT)}:{node.lineno}:{node.name}")

    assert missing == []
