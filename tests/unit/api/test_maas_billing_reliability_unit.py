"""Unit tests for Stripe reliability wrapper in src.api.maas_billing."""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.core.resilience.reliability_policy import CircuitBreakerOpen, RetryExhausted


def test_billing_readiness_ready_when_db_and_stripe_configured(monkeypatch):
    import src.api.maas_billing as mod

    db = MagicMock(spec=["query", "commit", "add"])
    monkeypatch.setattr(mod, "STRIPE_SECRET_KEY", "sk_test_ready")
    monkeypatch.setattr(mod, "_missing_plans", [])
    monkeypatch.setattr(mod, "usage_metering_service", object())
    monkeypatch.setattr(mod, "_get_mesh_or_404", lambda *_args, **_kwargs: object())

    payload = mod._billing_readiness_status(db)

    assert payload["status"] == "ready"
    assert payload["route_registered"] is True
    assert payload["lifecycle_binding"] == "route_import_only"
    assert payload["startup_hook_completed"] is None
    assert payload["write_db_ready"] is True
    assert payload["stripe_config_ready"] is True
    assert payload["stripe_plans_ready"] is True
    assert payload["legacy_metering_ready"] is True
    assert payload["degraded_dependencies"] == []


def test_billing_readiness_degraded_when_db_stripe_and_legacy_missing(monkeypatch):
    import src.api.maas_billing as mod

    monkeypatch.setattr(mod, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(mod, "_missing_plans", ["starter"])
    monkeypatch.setattr(mod, "usage_metering_service", None)
    monkeypatch.setattr(mod, "_get_mesh_or_404", None)

    payload = mod._billing_readiness_status(SimpleNamespace())

    assert payload["status"] == "degraded"
    assert payload["write_db_ready"] is False
    assert payload["stripe_config_ready"] is False
    assert payload["stripe_plans_ready"] is False
    assert payload["legacy_metering_ready"] is False
    assert payload["degraded_dependencies"] == [
        "database",
        "stripe",
        "stripe_plans",
        "legacy_maas_metering",
    ]
    assert "live Stripe API reachability" in payload["claim_boundary"]


def test_billing_readiness_endpoint_marks_degraded_dependencies(monkeypatch):
    import src.api.maas_billing as mod

    monkeypatch.setattr(mod, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(mod, "_missing_plans", ["starter", "pro"])
    monkeypatch.setattr(mod, "usage_metering_service", object())
    monkeypatch.setattr(mod, "_get_mesh_or_404", lambda *_args, **_kwargs: object())

    request = SimpleNamespace(state=SimpleNamespace())
    payload = asyncio.run(mod.billing_readiness(request=request, db=SimpleNamespace()))

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"database", "stripe", "stripe_plans"}


def test_execute_stripe_call_success(monkeypatch):
    import src.api.maas_billing as mod

    async def _fake_call_with_reliability(operation, **_kwargs):
        return await operation()

    async def _operation():
        return {"id": "ok"}

    monkeypatch.setattr(mod, "call_with_reliability", _fake_call_with_reliability)

    result = asyncio.run(mod._execute_stripe_call(_operation))
    assert result == {"id": "ok"}


def test_execute_stripe_call_marks_degraded_when_circuit_open(monkeypatch):
    import src.api.maas_billing as mod

    async def _raise_circuit_open(*_args, **_kwargs):
        raise CircuitBreakerOpen("open")

    monkeypatch.setattr(mod, "call_with_reliability", _raise_circuit_open)

    request = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(mod._execute_stripe_call(lambda: None, request=request))

    assert exc.value.status_code == 503
    assert "stripe" in request.state.degraded_dependencies


def test_execute_stripe_call_marks_degraded_when_retries_exhausted(monkeypatch):
    import src.api.maas_billing as mod

    async def _raise_retry_exhausted(*_args, **_kwargs):
        raise RetryExhausted("exhausted")

    monkeypatch.setattr(mod, "call_with_reliability", _raise_retry_exhausted)

    request = SimpleNamespace(state=SimpleNamespace())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(mod._execute_stripe_call(lambda: None, request=request))

    assert exc.value.status_code == 503
    assert "stripe" in request.state.degraded_dependencies
