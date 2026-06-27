import hashlib
import subprocess
from types import SimpleNamespace

import pytest

from src.coordination.events import EventBus, EventType
from src.network import vpn_watchdog as mod


def _use_bus(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(mod, "_EVENT_BUS", bus)
    monkeypatch.setattr(mod, "_EVENT_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(mod, "_SOURCE_AGENT", mod.VPN_WATCHDOG_SERVICE_NAME)
    return bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod.VPN_WATCHDOG_SERVICE_NAME,
        limit=100,
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
    payload = _stage_payload(bus, "vpn_watchdog_provider_guard_blocked")

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


def test_connection_states_publishes_counts_and_redacted_output(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)
    server = "secret-vpn-server"
    stdout = (
        "ESTAB 0 0 secret-vpn-server\n"
        "FIN-WAIT-2 0 0 secret-vpn-server\n"
        "CLOSE-WAIT 0 0 secret-vpn-server\n"
        "LAST-ACK 0 0 secret-vpn-server\n"
    )
    stderr = "secret ss stderr"

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

    states = mod.check_connection_states()
    payload = _stage_payload(bus, "vpn_watchdog_connection_states_observed")

    assert states == {"ESTAB": 1, "FIN-WAIT-2": 1, "CLOSE-WAIT": 1, "LAST-ACK": 1}
    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["counts"] == states
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


def test_curl_proxy_health_publishes_redacted_output_and_latency(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)
    stdout = "0.123 204"
    stderr = "secret curl stderr"

    monkeypatch.setattr(mod, "SOCKS_HOST", "secret-socks-host")
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

    assert mod._curl_proxy_health(10918) == (True, pytest.approx(123.0))
    payload = _stage_payload(bus, "vpn_watchdog_curl_proxy_observed")

    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["proxy_ok"] is True
    assert payload["parsed_summary"]["latency_ms"] == 123.0
    assert payload["socks_host_hash"] == hashlib.sha256(
        b"secret-socks-host"
    ).hexdigest()
    assert payload["socks_port_hash"] == hashlib.sha256(b"10918").hexdigest()
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    text = str(payload)
    assert "secret-socks-host" not in text
    assert stdout not in text
    assert stderr not in text
    assert "socks5h://" not in text


def test_proxy_health_detection_publishes_redacted_port_evidence(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)

    monkeypatch.setattr(mod, "SOCKS_HOST", "secret-socks-host")
    monkeypatch.setattr(mod, "SOCKS_PORT", 10808)
    monkeypatch.setattr(mod, "SOCKS_PORT_CANDIDATES", (10808, 10918))
    monkeypatch.setattr(mod, "discover_socks_port", lambda: 10918)
    monkeypatch.setattr(mod, "_curl_proxy_health", lambda port: (True, 42.0))

    assert mod.check_proxy_health() == (True, 42.0)
    payload = _stage_payload(bus, "vpn_watchdog_proxy_health_observed")

    assert payload["returncode"] == 0
    assert payload["source_mode"] == "curl"
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


def test_get_xray_pid_publishes_redacted_pid_and_pattern(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)
    stdout = "12345\n67890\n"
    pattern = "secret xray process pattern"

    monkeypatch.setattr(mod, "XRAY_PROCESS_PATTERN", pattern)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda cmd, **_kwargs: subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=stdout,
            stderr="secret pgrep stderr",
        ),
    )

    assert mod.get_xray_pid() == 12345
    payload = _stage_payload(bus, "vpn_watchdog_xray_pid_observed")

    assert payload["returncode"] == 0
    assert payload["parsed_summary"]["pid_found"] is True
    assert payload["pid_hash"] == hashlib.sha256(b"12345").hexdigest()
    assert payload["process_pattern_hash"] == hashlib.sha256(
        pattern.encode("utf-8")
    ).hexdigest()
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    text = str(payload)
    assert pattern not in text
    assert stdout not in text
    assert "secret pgrep stderr" not in text


def test_force_close_stale_publishes_redacted_local_actuator_evidence(
    monkeypatch,
    tmp_path,
):
    bus = _use_bus(monkeypatch, tmp_path)
    server = "secret-vpn-server"
    stdout = b"secret close stdout"

    monkeypatch.setattr(mod, "VPN_SERVER", server)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda cmd, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr=b"",
        ),
    )

    mod.VPNHealer().force_close_stale()
    payloads = [
        event.data
        for event in _events(bus)
        if event.data["stage"] == "vpn_watchdog_force_close_completed"
    ]

    assert len(payloads) == 2
    assert all(payload["control_action"] is True for payload in payloads)
    assert payloads[0]["command_shape"][:4] == ["ss", "-K", "dst", "<vpn_server>"]
    assert payloads[0]["vpn_server_hash"] == hashlib.sha256(
        server.encode("utf-8")
    ).hexdigest()
    assert payloads[0]["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout
    ).hexdigest()
    text = str(payloads)
    assert server not in text
    assert "secret close stdout" not in text


def test_restart_xray_hard_heal_disabled_publishes_skip(monkeypatch, tmp_path):
    bus = _use_bus(monkeypatch, tmp_path)

    monkeypatch.setattr(mod, "ENABLE_HARD_HEAL", False)
    monkeypatch.setattr(
        mod.os,
        "kill",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("SIGTERM should not run")
        ),
    )

    assert mod.VPNHealer().restart_xray() is False
    payload = _stage_payload(bus, "vpn_watchdog_restart_hard_heal_disabled")

    assert payload["control_action"] is False
    assert payload["returncode"] == 1
    assert payload["parsed_summary"]["hard_heal_enabled"] is False
