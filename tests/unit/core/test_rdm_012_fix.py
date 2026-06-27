import pytest
from unittest.mock import MagicMock

import src.core.production_lifespan as mod


@pytest.mark.asyncio
async def test_guardrail_failure_does_not_fail_open_in_production(monkeypatch):
    """
    RDM-012: Ensure that if guardrails fail in production, we do NOT fail open
    even if fail-open is theoretically allowed for other errors.
    """
    # 1. Setup production environment
    dummy_settings = MagicMock()
    dummy_settings.is_production.return_value = True
    dummy_settings.is_testing.return_value = False
    dummy_settings.security_profile.return_value = {
        "mtls_enabled": True,
        "rate_limit_enabled": True,
        "request_validation_enabled": True,
    }
    monkeypatch.setattr(mod, "settings", dummy_settings)

    # 2. Trigger guardrail failure by unsetting DB_ENFORCE_SCHEMA
    monkeypatch.delenv("DB_ENFORCE_SCHEMA", raising=False)
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")
    monkeypatch.setenv("MAAS_LIGHT_MODE", "false")
    monkeypatch.setenv("X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY", "false")
    # Force testing_mode to False even though we are in pytest
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("TESTING", "false")

    # Even if fail-open is enabled, guardrail violation should crash the app
    monkeypatch.setenv("X0TTA6BL4_FAIL_OPEN_STARTUP", "true")

    engine = mod.OptimizationEngine()

    # We expect a RuntimeError from _validate_enterprise_guardrails
    # And it should NOT be caught by the fail-open block in a way that returns normally.
    with pytest.raises(RuntimeError, match="DB_ENFORCE_SCHEMA must be explicitly set"):
        await engine.startup()


@pytest.mark.asyncio
async def test_explicit_db_enforce_schema_requirement(monkeypatch):
    """
    Verify that DB_ENFORCE_SCHEMA must be explicitly set in production.
    """
    dummy_settings = MagicMock()
    dummy_settings.is_production.return_value = True
    dummy_settings.is_testing.return_value = False
    dummy_settings.security_profile.return_value = {
        "mtls_enabled": True,
        "rate_limit_enabled": True,
        "request_validation_enabled": True,
    }
    monkeypatch.setattr(mod, "settings", dummy_settings)
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")
    monkeypatch.setenv("MAAS_LIGHT_MODE", "false")
    monkeypatch.setenv("X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY", "false")

    # Case A: Missing -> Raise
    monkeypatch.delenv("DB_ENFORCE_SCHEMA", raising=False)
    with pytest.raises(RuntimeError, match="DB_ENFORCE_SCHEMA must be explicitly set"):
        mod._validate_enterprise_guardrails(testing_mode=False)

    # Case B: Set to false -> Raise
    monkeypatch.setenv("DB_ENFORCE_SCHEMA", "false")
    with pytest.raises(RuntimeError, match="DB_ENFORCE_SCHEMA must be true"):
        mod._validate_enterprise_guardrails(testing_mode=False)

    # Case C: Set to true -> OK
    monkeypatch.setenv("DB_ENFORCE_SCHEMA", "true")
    assert mod._validate_enterprise_guardrails(testing_mode=False) is True
