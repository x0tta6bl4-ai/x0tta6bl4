"""Top-level package for libx0t.

Keep high-level SDK imports lazy so submodule imports do not require optional
runtime dependencies.
"""

from __future__ import annotations

from typing import Any

__version__ = "0.1.0-alpha"
__all__ = ["X0T", "MeshTunnel", "default_x0t"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .x0t import MeshTunnel, X0T, default_x0t

        exports = {
            "X0T": X0T,
            "MeshTunnel": MeshTunnel,
            "default_x0t": default_x0t,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
