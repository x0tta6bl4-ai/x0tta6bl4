"""Lightweight API package exports.

Submodules are imported only when requested. This keeps unrelated routers from
performing environment checks while another API module is being imported.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

__all__ = ["users", "billing", "vpn"]


def __getattr__(name: str) -> ModuleType | None:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = import_module(f"{__name__}.{name}")
    except Exception:
        module = None
    globals()[name] = module
    return module
