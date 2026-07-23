"""Public licensing helpers for x0tta6bl4 node activation."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_LAZY_EXPORTS = {
    "DeviceFingerprint": "src.licensing.node_identity",
    "HardwareFingerprinter": "src.licensing.node_identity",
    "IdentityCertificate": "src.licensing.node_identity",
    "LicenseActivationError": "src.licensing.node_identity",
    "LicenseAuthority": "src.licensing.node_identity",
    "MeshNetworkValidator": "src.licensing.node_identity",
    "NodeLicenseManager": "src.licensing.node_identity",
    "main": "src.licensing.node_identity",
}

__all__ = sorted(_LAZY_EXPORTS)


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'src.licensing' has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
