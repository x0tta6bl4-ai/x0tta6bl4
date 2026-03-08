"""Unit tests for Stripe reliability wrapper in src.api.maas_billing."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.core.reliability_policy import CircuitBreakerOpen, RetryExhausted


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
