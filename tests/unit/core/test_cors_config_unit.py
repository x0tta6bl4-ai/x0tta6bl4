"""Unit tests for production-safe CORS configuration helpers."""

import pytest

from src.core.cors_config import (is_effective_production_mode,
                                  resolve_cors_allowed_origins)


def test_resolve_cors_origins_defaults_to_localhost_in_non_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("X0TTA6BL4_PRODUCTION", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert resolve_cors_allowed_origins() == [
        "http://localhost:3000",
        "http://localhost:8000",
    ]


def test_resolve_cors_origins_uses_explicit_allowlist_in_non_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("X0TTA6BL4_PRODUCTION", raising=False)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173, https://preview.example.org",
    )

    assert resolve_cors_allowed_origins() == [
        "http://localhost:5173",
        "https://preview.example.org",
    ]


def test_resolve_cors_origins_requires_allowlist_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        resolve_cors_allowed_origins()


def test_resolve_cors_origins_rejects_wildcard_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="Wildcard CORS origin"):
        resolve_cors_allowed_origins()


def test_resolve_cors_origins_rejects_http_origins_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://app.example.com,http://legacy.example.com",
    )

    with pytest.raises(RuntimeError, match="HTTPS only"):
        resolve_cors_allowed_origins()


def test_resolve_cors_origins_accepts_https_allowlist_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://app.example.com,https://admin.example.com",
    )

    assert resolve_cors_allowed_origins() == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_production_flag_enables_effective_production_mode(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")

    assert is_effective_production_mode() is True
