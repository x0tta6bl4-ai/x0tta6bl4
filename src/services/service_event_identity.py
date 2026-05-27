"""Helpers for attaching canonical service identity to emitted events."""

from __future__ import annotations

import os
from typing import Dict, Iterable, Optional, Tuple


_GENERIC_IDENTITY_ENV: Dict[str, Tuple[str, ...]] = {
    "spiffe_id": (
        "X0TTA6BL4_SERVICE_SPIFFE_ID",
        "SERVICE_SPIFFE_ID",
        "SPIFFE_ID",
    ),
    "did": (
        "X0TTA6BL4_SERVICE_DID",
        "SERVICE_DID",
        "DID",
    ),
    "wallet_address": (
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "SERVICE_WALLET_ADDRESS",
        "GHOST_WALLET_ADDRESS",
    ),
}

_FIELD_SUFFIXES = {
    "spiffe_id": "SPIFFE_ID",
    "did": "DID",
    "wallet_address": "WALLET_ADDRESS",
}


def _service_prefix(service_name: str) -> str:
    return service_name.upper().replace("-", "_")


def _env_value(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        normalized = value.strip()
        if normalized:
            return normalized
    return None


def _identity_env_candidates(service_name: str, field: str) -> Tuple[str, ...]:
    return (
        f"{_service_prefix(service_name)}_{_FIELD_SUFFIXES[field]}",
        *_GENERIC_IDENTITY_ENV[field],
    )


def _identity_env_source(env_var: str) -> str:
    if env_var.startswith("X0TTA6BL4_SERVICE_"):
        return "x0tta6bl4_generic"
    if env_var.startswith("SERVICE_") or env_var in {"SPIFFE_ID", "DID"}:
        return "generic"
    if env_var == "GHOST_WALLET_ADDRESS":
        return "legacy_generic"
    return "service_specific"


def _configured_env(names: Iterable[str]) -> tuple[Optional[str], Optional[str]]:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        if value.strip():
            return name, _identity_env_source(name)
    return None, None


def service_event_identity(*, service_name: str) -> Dict[str, Optional[str]]:
    """Resolve optional workload identity fields for background service events."""
    return {
        field: _env_value(*_identity_env_candidates(service_name, field))
        for field in _FIELD_SUFFIXES
    }


def service_event_identity_status(*, service_name: str) -> Dict[str, object]:
    """Report identity configuration presence without exposing identity values."""
    fields: Dict[str, Dict[str, object]] = {}
    for field in _FIELD_SUFFIXES:
        env_var, source = _configured_env(_identity_env_candidates(service_name, field))
        fields[field] = {
            "configured": env_var is not None,
            "source": source,
            "env_var": env_var,
        }

    configured_fields = sum(1 for item in fields.values() if item["configured"])
    return {
        "service_name": service_name,
        "env_prefix": _service_prefix(service_name),
        "fields": fields,
        "configured_fields": configured_fields,
        "complete": configured_fields == len(_FIELD_SUFFIXES),
        "redacted": True,
    }
