"""
Ghost Access Database — SQLAlchemy models and helpers.

The canonical implementation lives in:
    deploy_assets/database.py  (3 027 bytes)
    scripts/database.py        (3 073 bytes)

This root-level file re-exports for MCP tooling inventory
and convenience imports.

Status: Реализовано (deploy_assets/)
"""
from __future__ import annotations

import importlib.util as _ilu
from pathlib import Path as _P

_spec = _ilu.spec_from_file_location(
    "database_impl",
    _P(__file__).resolve().parent / "deploy_assets" / "database.py",
)

if _spec and _spec.loader:
    _mod = _ilu.module_from_spec(_spec)
    try:
        _spec.loader.exec_module(_mod)
        globals().update(
            {k: v for k, v in vars(_mod).items() if not k.startswith("_")}
        )
    except Exception:
        pass  # graceful
