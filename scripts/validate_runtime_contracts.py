#!/usr/bin/env python3
"""
Validate runtime API contract invariants for CI.

Checks:
1) No duplicate (method, path) registrations in FastAPI app routes.
2) Required compatibility and canonical endpoints are present.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Iterable, Tuple


def _normalize_methods(methods: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted(m for m in methods if m not in {"HEAD", "OPTIONS"}))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Keep import-time side effects minimal during CI validation.
    os.environ.setdefault("MAAS_LIGHT_MODE", "true")
    os.environ.setdefault("ENVIRONMENT", "testing")
    os.environ.setdefault("DB_ENFORCE_SCHEMA", "false")

    from src.core.app import app

    route_index: DefaultDict[Tuple[str, str], list[int]] = defaultdict(list)
    for idx, route in enumerate(app.routes):
        methods = getattr(route, "methods", None)
        if not methods:
            continue
        for method in _normalize_methods(methods):
            route_index[(method, route.path)].append(idx)

    duplicates = {k: v for k, v in route_index.items() if len(v) > 1}
    if duplicates:
        print("Duplicate method+path routes detected:")
        for (method, path), idxs in sorted(duplicates.items()):
            print(f"  - {method} {path}: registrations={idxs}")
        return 1

    required_routes = [
        ("POST", "/api/v1/maas/auth/register"),
        ("POST", "/api/v1/maas/deploy"),
        ("POST", "/api/v1/maas/mesh/deploy"),
        ("POST", "/api/v1/maas/billing/pay"),
        ("POST", "/api/v3/maas/auth/register"),
    ]

    missing = [key for key in required_routes if key not in route_index]
    if missing:
        print("Missing required runtime routes:")
        for method, path in missing:
            print(f"  - {method} {path}")
        return 1

    import src
    import src.api.maas as maas
    from src.version import __version__ as canonical_version

    if src.__version__ != canonical_version:
        print(
            "Version mismatch: "
            f"src.__version__={src.__version__} "
            f"!= src.version.__version__={canonical_version}"
        )
        return 1
    if maas.__version__ != canonical_version:
        print(
            "Version mismatch: "
            f"src.api.maas.__version__={maas.__version__} "
            f"!= src.version.__version__={canonical_version}"
        )
        return 1

    print(
        "Runtime contract validation passed: "
        f"routes={len(app.routes)}, duplicate_method_path=0, version={canonical_version}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
