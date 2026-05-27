"""
SPIFFE/SPIRE Identity Management Module

SPIFFE (Secure Production Identity Framework for Everyone) provides
cryptographic identity for workloads in dynamic environments.

Components:
- Workload API: SVIDs (SPIFFE Verifiable Identity Documents)
- Agent: Node attestation and workload registration
- Controller: SPIRE server interaction and policy management

References:
- https://spiffe.io/
- https://github.com/spiffe/spire
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "0.1.0"
__all__ = [
    "SPIFFEController",
    "SPIREAgentManager",
    "AttestationStrategy",
    "WorkloadEntry",
]

_EXPORT_MODULES = {
    "SPIFFEController": ".controller",
    "SPIREAgentManager": ".agent",
    "AttestationStrategy": ".agent",
    "WorkloadEntry": ".agent",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
