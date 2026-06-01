import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/auto_rollback.py"
    spec = importlib.util.spec_from_file_location("auto_rollback_script", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class _FakeAsyncClient:
    def __init__(self, responses=None, exc=None):
        self.responses = list(responses or [])
        self.exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, timeout):
        if self.exc:
            raise self.exc
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_check_metrics_redacts_http_output_and_errors(monkeypatch):
    module = _load_module()
    health_body = '{"status":"ok","secret":"hidden"}'
    metrics_body = "production_error_rate 0.12\nsecret_metric 42\n"
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(
            responses=[
                _FakeResponse(200, health_body),
                _FakeResponse(200, metrics_body),
            ]
        ),
    )

    result = await module.AutoRollback().check_metrics()

    assert result["healthy"] is True
    assert result["error_rate"] == 0.12
    assert result["health_output_metadata"]["raw_output_retained"] is False
    assert result["metrics_output_metadata"]["raw_output_retained"] is False
    assert "secret_metric" not in str(result)
    assert "hidden" not in str(result)
    assert result["production_readiness_claim_allowed"] is False
    assert result["production_slo_claim_allowed"] is False
    metadata = result["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.ops.auto_rollback.safe_actuator_claim_gate.v1"
    assert claim_gate["local_health_observation_claim_allowed"] is True
    assert claim_gate["local_metrics_observation_claim_allowed"] is True
    assert claim_gate["live_rollback_execution_claim_allowed"] is False
    assert claim_gate["traffic_shift_claim_allowed"] is False


@pytest.mark.asyncio
async def test_check_metrics_redacts_exception_message(monkeypatch):
    module = _load_module()
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(exc=RuntimeError("secret-url")),
    )

    result = await module.AutoRollback().check_metrics()

    assert result["healthy"] is False
    assert result["error_type"] == "RuntimeError"
    assert result["raw_error_redacted"] is True
    assert "secret-url" not in str(result)
    assert (
        result["safe_actuator_evidence_metadata"]["claim_gate"][
            "production_readiness_claim_allowed"
        ]
        is False
    )


@pytest.mark.asyncio
async def test_execute_rollback_is_blocked_without_authorization(capsys):
    module = _load_module()
    rollback = module.AutoRollback(allow_live_rollback=False)

    result = await rollback.execute_rollback()

    output = capsys.readouterr().out
    assert "LIVE ROLLBACK: BLOCKED" in output
    assert "Current deployment stopped" not in output
    assert result["rollback_recommended"] is True
    assert result["rollback_executed"] is False
    assert result["live_rollback_authorized"] is False
    assert result["production_slo_claim_allowed"] is False
    claim_gate = result["safe_actuator_evidence_metadata"]["claim_gate"]
    assert claim_gate["local_rollback_recommendation_claim_allowed"] is True
    assert claim_gate["live_rollback_execution_claim_allowed"] is False


@pytest.mark.asyncio
async def test_authorized_placeholder_does_not_claim_live_rollback_execution(capsys):
    module = _load_module()
    rollback = module.AutoRollback(allow_live_rollback=True)

    result = await rollback.execute_rollback()

    output = capsys.readouterr().out
    assert "LIVE ROLLBACK: AUTHORIZED" in output
    assert "ROLLBACK COMMAND ADAPTER: NOT CONFIGURED" in output
    assert "Current deployment stopped" not in output
    assert result["rollback_recommended"] is True
    assert result["rollback_executed"] is False
    assert result["live_rollback_authorized"] is True
    assert result["live_rollback_executed"] is False
    assert result["rollback_command_adapter_configured"] is False
    claim_gate = result["safe_actuator_evidence_metadata"]["claim_gate"]
    assert claim_gate["local_rollback_recommendation_claim_allowed"] is True
    assert claim_gate["rollback_command_adapter_configured"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False


def test_auto_rollback_source_uses_recommendation_language_and_claim_boundary():
    text = (ROOT / "scripts/auto_rollback.py").read_text(encoding="utf-8")

    assert "AUTO-ROLLBACK MONITOR ACTIVE" not in text
    assert "EXECUTING ROLLBACK" not in text
    assert "ROLLBACK COMPLETE" not in text
    assert "ROLLBACK RECOMMENDATION" in text
    assert "X0TTA6BL4_ALLOW_LIVE_ROLLBACK" in text
    assert "x0tta6bl4.ops.auto_rollback.safe_actuator_claim_gate.v1" in text
    assert "production_readiness_claim_allowed" in text
    assert "raw_output_retained" in text
    assert "ROLLBACK COMMAND ADAPTER: NOT CONFIGURED" in text
