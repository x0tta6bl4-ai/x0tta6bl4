"""Compatibility export for MaaS compatibility routes and readiness helpers."""

from src.api.maas.endpoints import compat as modular
from src.api.maas.endpoints.compat import *  # noqa: F401,F403

router = modular.router

_compat_auth_alias_available = modular._compat_auth_alias_available
_compat_legacy_deploy_available = modular._compat_legacy_deploy_available
_compat_billing_alias_available = modular._compat_billing_alias_available
_compat_models_available = modular._compat_models_available


def _sync_readiness_helpers() -> None:
    modular._compat_auth_alias_available = _compat_auth_alias_available
    modular._compat_legacy_deploy_available = _compat_legacy_deploy_available
    modular._compat_billing_alias_available = _compat_billing_alias_available
    modular._compat_models_available = _compat_models_available


def _compat_readiness_status(db):
    _sync_readiness_helpers()
    status = modular._compat_readiness_status(db)
    if "cross_plane_claim_gate" not in status:
        status["cross_plane_claim_gate"] = modular.readiness_cross_plane_claim_gate_metadata(
            surface="maas_compat_readiness"
        )
    return status


async def maas_compat_readiness(request, db):
    _sync_readiness_helpers()
    return await modular.maas_compat_readiness(request, db)
