import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    if "production_monitor_script" in sys.modules:
        return sys.modules["production_monitor_script"]

    path = ROOT / "scripts/production_monitor.py"
    spec = importlib.util.spec_from_file_location("production_monitor_script", path)
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
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, timeout):
        if self.exc:
            raise self.exc
        return self.response


@pytest.mark.asyncio
async def test_health_check_redacts_errors_and_records_duration(monkeypatch):
    module = _load_module()
    secret_error = RuntimeError("secret-token http://internal.example")
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda: _FakeAsyncClient(exc=secret_error),
    )

    result = await module.ProductionMonitor("http://localhost:8080").check_health()

    assert result["healthy"] is False
    assert result["error_type"] == "RuntimeError"
    assert result["raw_error_redacted"] is True
    assert result["raw_output_retained"] is False
    assert "duration_ms" in result
    assert "secret-token" not in str(result)
    assert "http://internal.example" not in str(result)


@pytest.mark.asyncio
async def test_metrics_check_keeps_bounded_output_metadata(monkeypatch):
    module = _load_module()
    raw_metrics = "# HELP test\nproduction_error_rate 0.02\nsecret_metric 123\n"
    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda: _FakeAsyncClient(response=_FakeResponse(200, raw_metrics)),
    )

    result = await module.ProductionMonitor("http://localhost:8080").check_metrics()

    assert result["available"] is True
    assert result["error_rate"] == 0.02
    assert result["bounded_output_metadata"]["bytes"] == len(raw_metrics)
    assert result["bounded_output_metadata"]["raw_output_retained"] is False
    assert "sha256" in result["bounded_output_metadata"]
    assert "secret_metric" not in str(result)


@pytest.mark.asyncio
async def test_monitor_result_is_not_production_proof():
    module = _load_module()

    result = await module.ProductionMonitor().monitor(
        duration_minutes=0,
        interval_seconds=1,
    )

    assert result["checks"] == 0
    assert result["production_readiness_claim_allowed"] is False
    assert result["production_slo_claim_allowed"] is False
    assert result["live_customer_traffic_proven"] is False
    assert result["traffic_shift_claim_allowed"] is False
    assert result["external_dpi_bypass_confirmed"] is False
    assert result["settlement_finality_confirmed"] is False
    assert "does not prove live customer traffic" in result["claim_boundary"]


def test_monitor_shell_script_has_observation_boundary():
    text = (ROOT / "scripts/monitor_production.sh").read_text(encoding="utf-8")

    assert 'VPS_IP="${1:-89.125.1.107}"' not in text
    assert "PRODUCTION MONITORING OBSERVATION" in text
    assert "X0TTA6BL4_MONITOR_HOST" in text
    assert "raw_output_retained=false" in text
    assert "Monitoring complete!" not in text
    assert "not production readiness proof" in text
