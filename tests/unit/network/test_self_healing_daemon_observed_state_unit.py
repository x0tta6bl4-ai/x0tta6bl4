import hashlib
import subprocess
from types import SimpleNamespace

from src.coordination.events import EventBus, EventType
from src.network import self_healing_daemon as mod


def _use_bus(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(mod, "_EVENT_BUS", bus)
    monkeypatch.setattr(mod, "_EVENT_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(
        mod,
        "_SOURCE_AGENT",
        mod.NETWORK_SELF_HEALING_DAEMON_SERVICE_NAME,
    )
    return bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod.NETWORK_SELF_HEALING_DAEMON_SERVICE_NAME,
        limit=50,
    )


def _stage_payload(bus, stage):
    matches = [event.data for event in _events(bus) if event.data["stage"] == stage]
    assert matches, f"missing stage {stage}"
    return matches[-1]


def test_provider_guard_blocked_publishes_redacted_subprocess_evidence(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)
    script_path = "/secret/provider_guard.py"
    stdout = "BLOCK: secret provider outage 10.0.0.1"

    monkeypatch.setattr(mod, "PROVIDER_GUARD_DISABLED", False)
    monkeypatch.setattr(mod, "PROVIDER_GUARD_REQUIRE_FRESH", False)
    monkeypatch.setattr(mod, "PROVIDER_GUARD_SCRIPT", script_path)
    monkeypatch.setattr(mod.os.path, "exists", lambda _path: True)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda cmd, **_kwargs: subprocess.CompletedProcess(
            args=cmd,
            returncode=10,
            stdout=stdout,
            stderr="secret stderr",
        ),
    )

    allowed, reason = mod.provider_guard_allows_heal()
    payload = _stage_payload(bus, "network_self_healing_provider_guard_blocked")

    assert allowed is False
    assert "provider outage" in reason
    assert payload["returncode"] == 10
    assert payload["command_shape"] == [
        "<python>",
        "<provider_guard_script>",
        "--check",
        "--max-age-seconds",
        "<seconds>",
    ]
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["script_path_hash"] == hashlib.sha256(
        script_path.encode("utf-8")
    ).hexdigest()
    assert payload["identity"]["redacted"] is True
    text = str(payload)
    assert script_path not in text
    assert stdout not in text
    assert "secret stderr" not in text
    assert "10.0.0.1" not in text


def test_ping_success_publishes_redacted_latency_evidence(monkeypatch, tmp_path):
    bus = _use_bus(monkeypatch, tmp_path)
    target = "secret-target.example"
    interface = "secret-iface0"
    output = "64 bytes from secret-target.example: time=42.5 ms"

    monkeypatch.setattr(
        mod.subprocess,
        "check_output",
        lambda *_args, **_kwargs: output,
    )

    assert mod.ping_target(target, interface) == 42.5
    payload = _stage_payload(bus, "network_self_healing_ping_succeeded")

    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["latency_ms"] == 42.5
    assert payload["command_shape"][-1] == "<target>"
    assert payload["target_hash"] == hashlib.sha256(
        target.encode("utf-8")
    ).hexdigest()
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        output.encode("utf-8")
    ).hexdigest()
    text = str(payload)
    assert target not in text
    assert interface not in text
    assert output not in text


def test_proxy_health_detection_publishes_redacted_socket_evidence(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)

    monkeypatch.setattr(mod, "SOCKS_HOST", "secret-socks-host")
    monkeypatch.setattr(mod, "SOCKS_PORT", 10808)
    monkeypatch.setattr(mod, "SOCKS_PORT_CANDIDATES", (10808, 10918))
    monkeypatch.setattr(mod, "discover_socks_port", lambda: 10918)

    assert mod.check_proxy_health() is True
    payload = _stage_payload(bus, "network_self_healing_proxy_available")

    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["proxy_ok"] is True
    assert payload["parsed_summary"]["port_changed"] is True
    assert payload["socks_host_hash"] == hashlib.sha256(
        b"secret-socks-host"
    ).hexdigest()
    assert payload["socks_port_hash"] == hashlib.sha256(b"10918").hexdigest()
    text = str(payload)
    assert "secret-socks-host" not in text
    assert "10918" not in text
    assert "10808" not in text


def test_fin_wait2_count_publishes_returncode_and_redacted_output(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)
    server = "secret-vpn-server"
    stdout = "FIN-WAIT-2 secret-vpn-server\nESTAB secret-vpn-server\n"
    stderr = "secret ss warning"

    monkeypatch.setattr(mod, "VPN_SERVER", server)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda cmd, **_kwargs: subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    assert mod.get_fin_wait2_count() == 1
    payload = _stage_payload(bus, "network_self_healing_fin_wait2_observed")

    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["fin_wait2_count"] == 1
    assert payload["command_shape"] == ["ss", "-tn", "dst", "<vpn_server>"]
    assert payload["vpn_server_hash"] == hashlib.sha256(
        server.encode("utf-8")
    ).hexdigest()
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["stderr_metadata"]["sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    text = str(payload)
    assert server not in text
    assert stdout not in text
    assert stderr not in text


def test_trigger_healing_publishes_redacted_local_actuator_evidence(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)
    reason = "secret reason with 10.0.0.1"
    server = "secret-vpn-server"
    stdout = b"secret close stdout"

    monkeypatch.setattr(mod, "ENABLE_HEAL", True)
    monkeypatch.setattr(mod, "ENABLE_PULSE_SHIFT", False)
    monkeypatch.setattr(mod, "ENABLE_REALITY_ROTATION", False)
    monkeypatch.setattr(mod, "_healing_attempts_count", 0)
    monkeypatch.setattr(mod, "_last_heal_time", -9999.0)
    monkeypatch.setattr(mod, "VPN_SERVER", server)
    monkeypatch.setattr(mod, "provider_guard_allows_heal", lambda: (True, "ALLOW"))
    monkeypatch.setattr(mod.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda cmd, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr=b"",
        ),
    )

    mod.trigger_healing(reason)
    started = _stage_payload(bus, "network_self_healing_trigger_started")
    force_close = _stage_payload(bus, "network_self_healing_force_close_completed")
    completed = _stage_payload(bus, "network_self_healing_trigger_completed")

    assert started["control_action"] is True
    assert started["reason_hash"] == hashlib.sha256(
        reason.encode("utf-8")
    ).hexdigest()
    assert force_close["returncode"] == 0
    assert force_close["command_shape"][:4] == ["ss", "-K", "dst", "<vpn_server>"]
    assert force_close["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout
    ).hexdigest()
    assert completed["parsed_summary"]["healing_stage"] == 1
    text = str(_events(bus))
    assert reason not in text
    assert "10.0.0.1" not in text
    assert server not in text
    assert "secret close stdout" not in text
