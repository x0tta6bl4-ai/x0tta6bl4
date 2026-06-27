"""x0tta6bl4 Core Package

Decentralized self-healing mesh network with Zero Trust security.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

__author__ = "x0tta6bl4 Team"

from .version import __version__

_LAZY_SUBMODULES = {"core", "monitoring", "network", "security", "ml"}


def __getattr__(name: str) -> Any:
    if name in _LAZY_SUBMODULES:
        if name in globals():
            return globals()[name]
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["core", "security", "network", "ml", "monitoring"]

