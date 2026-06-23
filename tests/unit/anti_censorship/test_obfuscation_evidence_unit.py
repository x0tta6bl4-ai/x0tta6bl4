from src.anti_censorship.obfuscation import (
    ObfuscationConfig,
    ObfuscationLayer,
    TrafficObfuscator,
)
from src.coordination.events import EventBus, EventType


def _payloads(bus: EventBus) -> list[dict]:
    return [
        event.data
        for event in bus.get_event_history(
            source_agent="anti-censorship-traffic-obfuscator",
            limit=20,
        )
    ]


def test_obfuscate_publishes_redacted_local_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    config = ObfuscationConfig(
        enabled_layers=[ObfuscationLayer.PADDING],
        min_packet_size=64,
        max_packet_size=96,
        padding_strategy="fixed",
    )
    obfuscator = TrafficObfuscator(config, event_bus=bus)
    secret_payload = b"secret-traffic-payload"

    result = obfuscator.obfuscate(secret_payload)
    payload = _payloads(bus)[0]
    text = repr(payload)

    assert isinstance(result, bytes)
    assert payload["component"] == "anti_censorship.obfuscation"
    assert payload["operation"] == "obfuscate"
    assert payload["status"] == "obfuscated"
    assert payload["service_name"] == "anti-censorship-traffic-obfuscator"
    assert payload["layer"] == "anti_censorship_traffic_obfuscation_local_evidence"
    assert payload["applied_layers"] == ["padding"]
    assert payload["result_shape"]["kind"] == "bytes"
    assert payload["payloads_redacted"] is True
    assert payload["raw_packets_redacted"] is True
    assert payload["raw_fragments_redacted"] is True
    assert payload["dataplane_confirmed"] is False
    assert payload["dpi_bypass_confirmed"] is False
    assert payload["bypass_confirmed"] is False
    assert payload["external_dpi_tested"] is False
    assert payload["service_identity"]["raw_identity_redacted"] is True
    assert "secret-traffic-payload" not in text


def test_deobfuscate_timing_and_stats_publish_redacted_evidence(tmp_path):
    bus = EventBus(str(tmp_path))
    config = ObfuscationConfig(
        enabled_layers=[ObfuscationLayer.PADDING, ObfuscationLayer.TIMING],
        min_packet_size=64,
        max_packet_size=96,
        padding_strategy="fixed",
        timing_delay_ms=10,
        timing_jitter_ms=0,
    )
    obfuscator = TrafficObfuscator(config, event_bus=bus)
    obfuscated = obfuscator.obfuscate(b"roundtrip-secret")

    restored = obfuscator.deobfuscate(obfuscated)
    delay = obfuscator.get_timing_delay()
    stats = obfuscator.get_stats()
    payloads = _payloads(bus)

    assert restored == b"roundtrip-secret"
    assert delay == 0.01
    assert stats["packet_count"] == 1
    assert [p["operation"] for p in payloads] == [
        "obfuscate",
        "deobfuscate",
        "get_timing_delay",
        "get_stats",
    ]
    assert payloads[1]["status"] == "deobfuscated"
    assert payloads[1]["reversed_layers"] == ["padding"]
    assert payloads[2]["timing_enabled"] is True
    assert payloads[2]["raw_timing_trace_redacted"] is True
    assert payloads[3]["packet_count"] == 1
    assert "roundtrip-secret" not in repr(payloads)


def test_obfuscate_failure_publishes_failed_event_without_payload_or_key(tmp_path):
    bus = EventBus(str(tmp_path))
    config = ObfuscationConfig(
        enabled_layers=[ObfuscationLayer.XOR],
        xor_key=b"super-secret-xor-key",
    )
    obfuscator = TrafficObfuscator(config, event_bus=bus)

    try:
        obfuscator.obfuscate("not-bytes")  # type: ignore[arg-type]
        assert False, "Expected TypeError for non-byte XOR input"
    except TypeError:
        pass

    failed_events = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="anti-censorship-traffic-obfuscator",
        limit=10,
    )

    assert len(failed_events) == 1
    payload = failed_events[0].data
    text = repr(payload)
    assert payload["operation"] == "obfuscate"
    assert payload["status"] == "obfuscate_failed"
    assert payload["error"]["type"] == "TypeError"
    assert payload["config"]["xor_key_present"] is True
    assert payload["config"]["raw_xor_key_redacted"] is True
    assert payload["payloads_redacted"] is True
    assert "not-bytes" not in text
    assert "super-secret-xor-key" not in text
