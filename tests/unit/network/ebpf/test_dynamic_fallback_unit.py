import importlib
import hashlib
import os
from types import SimpleNamespace

import pytest

from src.coordination.events import EventBus, EventType

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_import_smoke():
    try:
        mod = importlib.import_module("src.network.ebpf.dynamic_fallback")
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None


def test_latency_fallback_publishes_redacted_trigger_and_recovery_evidence(tmp_path):
    mod = importlib.import_module("src.network.ebpf.dynamic_fallback")
    bus = EventBus(project_root=str(tmp_path))
    controller = mod.DynamicFallbackController(
        latency_threshold_ms=100.0,
        cooldown_seconds=0.0,
        event_bus=bus,
    )
    node_id = "mesh-node-secret-1"

    for _ in range(10):
        controller.update_latency(node_id, 150.0)

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-dynamic-fallback",
        limit=10,
    )
    assert len(events) == 1
    trigger = events[-1].data
    assert trigger["stage"] == "fallback_triggered"
    assert trigger["operation"] == "dynamic_fallback_trigger"
    assert trigger["active_fallback"] is True
    assert trigger["target_node_id_hash"] == hashlib.sha256(
        node_id.encode("utf-8")
    ).hexdigest()
    assert trigger["target_node_id_redacted"] is True
    assert trigger["payloads_redacted"] is True
    assert trigger["safe_observation"] is True
    assert trigger["recent_sample_count"] == 10
    assert trigger["spike_count"] == 10
    assert trigger["thinking"]["profile"]["role"] == "healing"
    assert trigger["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "ebpf_dynamic_fallback_trigger"
    )
    assert node_id not in str(trigger)

    for _ in range(10):
        controller.update_latency(node_id, 20.0)
    controller.check_recovery(node_id)

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-dynamic-fallback",
        limit=10,
    )
    assert len(events) == 2
    recovery = events[-1].data
    assert recovery["stage"] == "fallback_recovered"
    assert recovery["operation"] == "dynamic_fallback_recover"
    assert recovery["active_fallback"] is False
    assert recovery["target_node_id_hash"] == trigger["target_node_id_hash"]
    assert recovery["recovery_count"] == 10
    assert recovery["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "ebpf_dynamic_fallback_recover"
    )
    assert node_id not in str(recovery)


def test_mapek_integration_reuses_event_bus_for_fallback_evidence(tmp_path):
    mod = importlib.import_module("src.network.ebpf.dynamic_fallback")
    bus = EventBus(project_root=str(tmp_path))

    controller = mod.integrate_fallback_with_mapek(
        SimpleNamespace(event_bus=bus),
        ebpf_exporter=object(),
    )

    assert controller.event_bus is bus
