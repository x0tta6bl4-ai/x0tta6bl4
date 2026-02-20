"""
Backward-compatible MaaS module.

Primary implementation remains in `src.api.maas_legacy` for runtime/test
compatibility. Router aggregation keeps core endpoints wired as well.

Legacy router is included FIRST so its routes (/deploy, /register, /login,
/billing/webhook, etc.) take precedence over overlapping modular ones.
"""

from fastapi import APIRouter

from src.api import maas_legacy as _legacy
from src.api.maas_legacy import *  # noqa: F401,F403
from src.api.maas_core import router as _core_router


# Explicit exports for symbols that are prefixed with "_" in legacy module but
# are imported directly by compatibility tests/callers or modular sub-modules.
PQC_SEGMENT_PROFILES = _legacy.PQC_SEGMENT_PROFILES
_PQC_DEFAULT_PROFILE = _legacy._PQC_DEFAULT_PROFILE
_get_pqc_profile = _legacy._get_pqc_profile
_mesh_registry = _legacy._mesh_registry  # noqa: F401
_get_mesh_or_404 = _legacy._get_mesh_or_404  # noqa: F401  — used by maas_billing
usage_metering_service = _legacy.usage_metering_service  # noqa: F401  — used by maas_billing, maas_analytics


# Combined router – legacy first to ensure route precedence.
router = APIRouter()
router.include_router(_legacy.router)
router.include_router(_core_router)


__all__ = [name for name in globals() if not name.startswith("_")]
