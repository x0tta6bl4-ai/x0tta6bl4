"""Guards against re-introducing src.network imports into libx0t.network."""

from __future__ import annotations

import ast
from pathlib import Path


def test_libx0t_network_has_no_src_network_imports() -> None:
    root = Path("libx0t/network")
    offenders: list[str] = []

    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("src.network"):
                    offenders.append(f"{path}:{node.lineno} from {module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("src.network"):
                        offenders.append(
                            f"{path}:{node.lineno} import {alias.name}"
                        )

    assert offenders == [], "Found forbidden src.network imports:\n" + "\n".join(offenders)
