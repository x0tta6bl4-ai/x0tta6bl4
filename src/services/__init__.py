"""
Services Module
===============
Сервисы для управления узлами и интеграции с внешними системами.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["NodeManagerService", "UserNode", "get_node_manager"]


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module("src.services.node_manager_service")
    value = getattr(module, name)
    globals()[name] = value
    return value
