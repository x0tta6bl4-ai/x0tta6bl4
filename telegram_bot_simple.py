"""
Ghost Access Telegram Bot — simplified entry point.

The canonical implementation lives in:
    deploy_assets/telegram_bot_simple.py  (11 181 bytes, production)

This root-level file re-exports for MCP tooling inventory
and convenience imports.

Status: Реализовано (deploy_assets/)
"""
from __future__ import annotations

# Re-export from canonical location
import importlib.util as _ilu
from pathlib import Path as _P

_spec = _ilu.spec_from_file_location(
    "telegram_bot_simple_impl",
    _P(__file__).resolve().parent / "deploy_assets" / "telegram_bot_simple.py",
)

if _spec and _spec.loader:
    _mod = _ilu.module_from_spec(_spec)
    try:
        _spec.loader.exec_module(_mod)
        globals().update(
            {k: v for k, v in vars(_mod).items() if not k.startswith("_")}
        )
    except Exception:
        pass  # graceful — module is importable but deps may be missing at dev time
