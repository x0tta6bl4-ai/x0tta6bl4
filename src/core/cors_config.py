"""CORS configuration helpers with production-safe defaults."""

from __future__ import annotations

import os
from typing import List

from src.core.settings import settings


_TRUE_VALUES = {"1", "true", "yes", "on"}
_PRODUCTION_ENV_VALUES = {"production", "prod", "live"}
_DEV_FALLBACK_ORIGINS = ["http://localhost:3000", "http://localhost:8000"]


def is_effective_production_mode() -> bool:
    """Resolve production mode from environment settings and explicit flags."""
    environment = os.getenv("ENVIRONMENT", settings.environment).strip().lower()
    if environment in _PRODUCTION_ENV_VALUES:
        return True

    production_flag = os.getenv("X0TTA6BL4_PRODUCTION", "").strip().lower()
    return production_flag in _TRUE_VALUES


def _parse_allowed_origins(raw_value: str) -> List[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


def resolve_cors_allowed_origins() -> List[str]:
    """
    Resolve CORS origins with strict production validation.

    Production requirements:
    - explicit allowlist required (`CORS_ALLOWED_ORIGINS` must be non-empty)
    - wildcard origin (`*`) is forbidden
    - only HTTPS origins are allowed
    """
    raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    origins = _parse_allowed_origins(raw_origins)

    if not is_effective_production_mode():
        return origins or list(_DEV_FALLBACK_ORIGINS)

    if not origins:
        raise RuntimeError(
            "CORS_ALLOWED_ORIGINS must be explicitly set in production mode."
        )

    if "*" in origins:
        raise RuntimeError("Wildcard CORS origin '*' is not allowed in production mode.")

    insecure_origins = [origin for origin in origins if not origin.startswith("https://")]
    if insecure_origins:
        raise RuntimeError(
            "Production CORS origins must use HTTPS only. Invalid origins: "
            + ", ".join(insecure_origins)
        )

    return origins


__all__ = ["is_effective_production_mode", "resolve_cors_allowed_origins"]
