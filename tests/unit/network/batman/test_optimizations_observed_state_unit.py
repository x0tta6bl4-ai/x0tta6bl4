import hashlib
from unittest.mock import MagicMock

from src.coordination.events import EventBus, EventType
from src.network.batman import optimizations as mod


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod.BATMAN_OPTIMIZATIONS_SERVICE_NAME,
        limit=20,
    )


def _stage_payload(bus, stage):
    matches = [event.data for event in _events(bus) if event.data["stage"] == stage]
    assert matches, f"missing stage {stage}"
    return matches[-1]


def test_multipath_originators_success_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    config = mod.BatmanAdvConfig()
    router = mod.MultiPathRouter(config, event_bus=bus)
    destination = "secret-node"
    stdout = "originator-a\noriginator-b\n"
    stderr = "secret batctl warning"

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: MagicMock(
            returncode=0,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    assert router.discover_paths(destination) == 2
    payload = _stage_payload(bus, "batman_multipath_originators_collected")

    assert payload["service_name"] == mod.BATMAN_OPTIMIZATIONS_SERVICE_NAME
    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["paths_total"] == 2
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["stderr_metadata"]["sample_redacted"] is True
    assert payload["destination_hash"] == hashlib.sha256(
        destination.encode("utf-8")
    ).hexdigest()
    assert payload["destination_redacted"] is True
    assert payload["payloads_redacted"] is True
    text = str(payload)
    assert destination not in text
    assert stdout not in text
    assert stderr not in text


def test_multipath_originators_timeout_publishes_redacted_failure(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    router = mod.MultiPathRouter(mod.BatmanAdvConfig(), event_bus=bus)
    destination = "secret-timeout-node"

    def _timeout(*args, **kwargs):
        raise mod.subprocess.TimeoutExpired(["batctl", destination], 5)

    monkeypatch.setattr(mod.subprocess, "run", _timeout)

    assert router.discover_paths(destination) == 0
    payload = _stage_payload(bus, "batman_multipath_originators_timeout")
    assert payload["returncode"] == 124
    assert payload["error"]["type"] == "TimeoutExpired"
    assert payload["error"]["message_redacted"] is True
    assert destination not in str(payload)


def test_aodv_cached_route_probe_publishes_redacted_evidence(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    fallback = mod.AODVFallback(mod.BatmanAdvConfig(), event_bus=bus)
    destination = "secret-cached-route"
    fallback.route_cache[destination] = {"next_hop": "secret-hop"}
    stdout = "PING ok"
    stderr = "secret ping warning"

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: MagicMock(
            returncode=0,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    assert fallback.should_fallback(destination) is True
    payload = _stage_payload(bus, "batman_aodv_cached_route_probe_reachable")

    assert payload["operation"] == "should_fallback"
    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["route_cache_hit"] is True
    assert payload["parsed_summary"]["fallback"] is True
    assert payload["command_shape"][-1] == "<destination>"
    assert payload["stdout_metadata"]["bytes"] == len(stdout.encode("utf-8"))
    text = str(payload)
    assert destination not in text
    assert stdout not in text
    assert stderr not in text
    assert "secret-hop" not in text


def test_aodv_route_request_rate_limit_publishes_redacted_skip(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    config = mod.BatmanAdvConfig(aodv_route_request_retries=1)
    fallback = mod.AODVFallback(config, event_bus=bus)
    destination = "secret-rate-limited-route"
    fallback.active_requests[destination] = 1

    assert fallback.request_route(destination) is False
    payload = _stage_payload(bus, "batman_aodv_route_request_rate_limited")
    assert payload["status"] == "skipped"
    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["request_limit"] == 1
    assert payload["destination_redacted"] is True
    assert destination not in str(payload)


def test_optimizations_pass_event_bus_to_components(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    optimizations = mod.BatmanAdvOptimizations(event_bus=bus)

    assert optimizations.get_multipath_router().event_bus is bus
    assert optimizations.get_aodv_fallback().event_bus is bus
