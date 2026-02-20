"""
Backward-compatible shim for src.security.pqc_mtls.

The implementation lives in src.libx0t.security.pqc_mtls.
This shim keeps mutable globals/patch points working for legacy imports.
"""

import logging
from typing import Any, Dict

from src.libx0t.security import pqc_mtls as _impl

logger = logging.getLogger(__name__)
logger.warning(
    "DEPRECATED: src.security.pqc_mtls is moved to libx0t.security.pqc_mtls. "
    "Please update your imports."
)


PQCCertificate = _impl.PQCCertificate
get_pqc_hybrid = _impl.get_pqc_hybrid
_pqc_mtls_controller = _impl._pqc_mtls_controller


def _sync_impl_globals() -> None:
    """Mirror shim-level patch points into implementation module."""
    _impl.get_pqc_hybrid = get_pqc_hybrid
    _impl._pqc_mtls_controller = _pqc_mtls_controller


def _sync_shim_globals() -> None:
    """Mirror implementation state back into shim module globals."""
    global _pqc_mtls_controller
    _pqc_mtls_controller = _impl._pqc_mtls_controller


class PQCmTLSController(_impl.PQCmTLSController):
    """Wrapper that respects patched shim globals."""

    def __init__(self, enable_hybrid: bool = True):
        _sync_impl_globals()
        super().__init__(enable_hybrid=enable_hybrid)


def get_pqc_mtls_controller(enable_hybrid: bool = True) -> PQCmTLSController:
    """Get/create controller with legacy shim state synchronization."""
    global _pqc_mtls_controller
    if _pqc_mtls_controller is None:
        _pqc_mtls_controller = PQCmTLSController(enable_hybrid=enable_hybrid)
    _sync_impl_globals()
    _sync_shim_globals()
    return _pqc_mtls_controller


def test_pqc_mtls_setup() -> Dict[str, Any]:
    """Run setup test through shim-aware controller instance."""
    controller = get_pqc_mtls_controller()
    key_init = controller.initialize_pqc_keys()
    channel = controller.establish_pqc_channel()

    status = "success"
    if key_init.get("status") in {"disabled", "error"}:
        status = key_init.get("status", "error")

    return {
        "status": status,
        "mtls_controller_status": controller.get_status(),
        "key_initialization": key_init,
        "channel_establishment": channel,
        "overall_status": "success" if key_init.get("status") == "success" else "partial",
    }


__all__ = [
    "PQCCertificate",
    "PQCmTLSController",
    "get_pqc_hybrid",
    "get_pqc_mtls_controller",
    "test_pqc_mtls_setup",
    "_pqc_mtls_controller",
]
