"""Unit tests for demo API handlers without ASGI startup."""

import runpy
import sys
import types
from enum import Enum
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.core import demo_api


def _install_fake_ebpf_module(monkeypatch):
    fake_module = types.ModuleType("src.network.ebpf.explainer")

    class _EventType(Enum):
        PACKET_DROP = "packet_drop"
        HIGH_CPU_USAGE = "high_cpu_usage"

    class _Event:
        def __init__(self, event_type, timestamp, node_id, program_id, details):
            self.event_type = event_type
            self.timestamp = timestamp
            self.node_id = node_id
            self.program_id = program_id
            self.details = details
            self.human_readable = f"human:{event_type.name}"

    fake_module.EBPFEvent = _Event
    fake_module.EBPFEventType = _EventType
    monkeypatch.setitem(sys.modules, "src.network.ebpf.explainer", fake_module)
    return _EventType


def test_get_integrated_cycle_dependency_initializes_singleton(monkeypatch):
    calls = {"count": 0, "kwargs": None}
    fake_module = types.ModuleType("src.self_healing.mape_k_integrated")

    class _FakeCycle:
        def __init__(self, **kwargs):
            calls["count"] += 1
            calls["kwargs"] = kwargs

    fake_module.IntegratedMAPEKCycle = _FakeCycle
    monkeypatch.setitem(sys.modules, "src.self_healing.mape_k_integrated", fake_module)
    demo_api._integrated_cycle_instance = None

    first = demo_api.get_integrated_cycle_dependency()
    second = demo_api.get_integrated_cycle_dependency()

    assert first is second
    assert calls["count"] == 1
    assert calls["kwargs"] == {
        "enable_observe_mode": True,
        "enable_chaos": True,
        "enable_ebpf_explainer": True,
    }


@pytest.mark.asyncio
async def test_root_returns_expected_payload():
    payload = await demo_api.root()
    assert payload["name"] == "x0tta6bl4"
    assert payload["status"] == "operational"
    assert payload["components"]["mape_k"] == "integrated"


@pytest.mark.asyncio
async def test_get_status_uses_dependency_object():
    cycle = MagicMock()
    cycle.get_system_status.return_value = {"ok": True}

    result = await demo_api.get_status(cycle)

    assert result == {"ok": True}
    cycle.get_system_status.assert_called_once_with()


@pytest.mark.asyncio
async def test_demo_anomaly_detection_returns_json_response():
    cycle = MagicMock()
    cycle.run_cycle.return_value = {"result": "done"}

    response = await demo_api.demo_anomaly_detection({"node_id": "n1"}, cycle)

    assert response.status_code == 200
    assert response.body == b'{"result":"done"}'


@pytest.mark.asyncio
async def test_demo_anomaly_detection_wraps_error_as_http_500():
    cycle = MagicMock()
    cycle.run_cycle.side_effect = RuntimeError("boom")

    with pytest.raises(HTTPException) as exc:
        await demo_api.demo_anomaly_detection({"node_id": "n1"}, cycle)

    assert exc.value.status_code == 500
    assert "boom" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_get_observe_mode_stats_returns_404_when_disabled():
    cycle = MagicMock()
    cycle.observe_detector = None

    with pytest.raises(HTTPException) as exc:
        await demo_api.get_observe_mode_stats(cycle)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_demo_chaos_experiment_success():
    cycle = MagicMock()
    cycle.run_chaos_experiment.return_value = {"ok": True, "kind": "node_failure"}

    response = await demo_api.demo_chaos_experiment({}, cycle)

    assert response.status_code == 200
    assert response.body == b'{"ok":true,"kind":"node_failure"}'
    cycle.run_chaos_experiment.assert_called_once_with("node_failure", 10)


@pytest.mark.asyncio
async def test_demo_chaos_experiment_wraps_error_as_http_500():
    cycle = MagicMock()
    cycle.run_chaos_experiment.side_effect = RuntimeError("chaos boom")

    with pytest.raises(HTTPException) as exc:
        await demo_api.demo_chaos_experiment({"type": "network_partition"}, cycle)

    assert exc.value.status_code == 500
    assert exc.value.detail == "Internal server error"


@pytest.mark.asyncio
async def test_get_observe_mode_stats_success():
    cycle = MagicMock()
    cycle.observe_detector = MagicMock()
    cycle.observe_detector.get_stats.return_value = {"samples": 7}

    payload = await demo_api.get_observe_mode_stats(cycle)

    assert payload == {"samples": 7}


@pytest.mark.asyncio
async def test_get_chaos_stats_404_when_disabled():
    cycle = MagicMock()
    cycle.chaos_controller = None

    with pytest.raises(HTTPException) as exc:
        await demo_api.get_chaos_stats(cycle)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_chaos_stats_success():
    cycle = MagicMock()
    cycle.chaos_controller = MagicMock()
    cycle.chaos_controller.get_recovery_stats.return_value = {"recovered": 3}

    payload = await demo_api.get_chaos_stats(cycle)

    assert payload == {"recovered": 3}


@pytest.mark.asyncio
async def test_explain_ebpf_event_returns_404_when_disabled():
    cycle = MagicMock()
    cycle.ebpf_explainer = None

    with pytest.raises(HTTPException) as exc:
        await demo_api.explain_ebpf_event("packet_drop", cycle)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_explain_ebpf_event_success_for_known_event(monkeypatch):
    event_type = _install_fake_ebpf_module(monkeypatch)
    cycle = MagicMock()
    cycle.ebpf_explainer = MagicMock()
    cycle.ebpf_explainer.explain_event.return_value = "details"

    payload = await demo_api.explain_ebpf_event("packet_drop", cycle)

    assert payload["event_type"] == "packet_drop"
    assert payload["explanation"] == "details"
    assert payload["human_readable"] == "human:PACKET_DROP"
    passed_event = cycle.ebpf_explainer.explain_event.call_args[0][0]
    assert passed_event.event_type == event_type.PACKET_DROP


@pytest.mark.asyncio
async def test_explain_ebpf_event_falls_back_to_packet_drop_for_unknown(monkeypatch):
    event_type = _install_fake_ebpf_module(monkeypatch)
    cycle = MagicMock()
    cycle.ebpf_explainer = MagicMock()
    cycle.ebpf_explainer.explain_event.return_value = "fallback"

    payload = await demo_api.explain_ebpf_event("unknown-event", cycle)

    assert payload["explanation"] == "fallback"
    passed_event = cycle.ebpf_explainer.explain_event.call_args[0][0]
    assert passed_event.event_type == event_type.PACKET_DROP


@pytest.mark.asyncio
async def test_explain_ebpf_event_wraps_internal_error(monkeypatch):
    _install_fake_ebpf_module(monkeypatch)
    cycle = MagicMock()
    cycle.ebpf_explainer = MagicMock()
    cycle.ebpf_explainer.explain_event.side_effect = RuntimeError("explain boom")

    with pytest.raises(HTTPException) as exc:
        await demo_api.explain_ebpf_event("packet_drop", cycle)

    assert exc.value.status_code == 500
    assert exc.value.detail == "Internal server error"


def test_module_main_block_invokes_uvicorn_run(monkeypatch):
    uvicorn_module = types.ModuleType("uvicorn")
    calls = {}

    def _run(app, host, port):
        calls["app"] = app
        calls["host"] = host
        calls["port"] = port

    uvicorn_module.run = _run
    monkeypatch.setitem(sys.modules, "uvicorn", uvicorn_module)
    module_path = demo_api.__file__
    assert module_path is not None
    runpy.run_path(module_path, run_name="__main__")

    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 8081
    assert calls["app"] is not None
