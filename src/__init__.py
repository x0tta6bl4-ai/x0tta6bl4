"""x0tta6bl4 Core Package

Decentralized self-healing mesh network with Zero Trust security.
"""

__version__ = "1.0.0"
__author__ = "x0tta6bl4 Team"

# Import core modules immediately
from . import core, security, network, monitoring

# Lazy import ml module (heavy dependencies: torch, transformers, PEFT)
def __getattr__(name):
    if name == "ml":
        from . import ml
        return ml
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["core", "security", "network", "ml", "monitoring"]
