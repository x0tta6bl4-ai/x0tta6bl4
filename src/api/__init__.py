"""Lightweight API package exports.

Submodules are imported only when requested. This keeps unrelated routers from
performing environment checks while another API module is being imported.
"""
from __future__ import annotations

from importlib import import_module
from types import ModuleType
import os

_current_dir = os.path.dirname(__file__)
__all__ = sorted(list(set(
    [
        os.path.splitext(f)[0]
        for f in os.listdir(_current_dir)
        if f.endswith(".py") and f != "__init__.py"
    ]
    + [
        d
        for d in os.listdir(_current_dir)
        if os.path.isdir(os.path.join(_current_dir, d)) and not d.startswith("__")
    ]
)))


def __getattr__(name: str) -> ModuleType | None:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        module = import_module(f"{__name__}.{name}")
    except Exception:
        module = None
    globals()[name] = module
    return module

