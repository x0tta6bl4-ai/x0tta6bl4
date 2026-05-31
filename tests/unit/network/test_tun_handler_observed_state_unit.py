import hashlib
import subprocess
from types import SimpleNamespace

import pytest

from src.coordination.events import EventBus, EventType
from src.network import tun_handler as mod


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod.TUN_INTERFACE_SERVICE_NAME,
        limit=20,
    )


def _stage_payload(bus, stage):
    matches = [event.data for event in _events(bus) if event.data["stage"] == stage]
    assert matches, f"missing stage {stage}"
    return matches[-1]


@pytest.mark.asyncio
async def test_configure_interface_publishes_redacted_command_evidence(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    tun = mod.TUNInterface("secret-tun0", mtu=1420, event_bus=bus)
    stdout = "secret ip stdout"
    stderr = "secret ip stderr"

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    await tun._configure_interface()
    payload = _stage_payload(bus, "tun_interface_link_up_configured")

    assert payload["service_name"] == mod.TUN_INTERFACE_SERVICE_NAME
    assert payload["layer"] == mod.TUN_INTERFACE_LAYER
    assert payload["returncode"] == 0
    assert payload["duration_ms"] >= 0
    assert payload["command_shape"] == [
        "ip",
        "link",
        "set",
        "dev",
        "<interface>",
        "up",
    ]
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["stderr_metadata"]["sample_redacted"] is True
    assert payload["interface_hash"] == hashlib.sha256(
        b"secret-tun0"
    ).hexdigest()
    assert payload["interface_redacted"] is True
    assert payload["identity"]["redacted"] is True
    text = str(payload)
    assert "secret-tun0" not in text
    assert stdout not in text
    assert stderr not in text


@pytest.mark.asyncio
async def test_set_address_failure_publishes_redacted_output_and_ip_hashes(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    tun = mod.TUNInterface("secret-tun1", event_bus=bus)
    local_ip = "10.77.0.1/32"
    remote_ip = "10.77.0.2"
    stderr = "secret address already exists"

    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=2,
            stdout="",
            stderr=stderr,
        ),
    )

    assert await tun.set_address(local_ip, remote_ip) is False
    payload = _stage_payload(bus, "tun_interface_address_failed")

    assert payload["returncode"] == 2
    assert payload["command_shape"] == [
        "ip",
        "addr",
        "add",
        "<local_ip>",
        "peer",
        "<remote_ip>",
        "dev",
        "<interface>",
    ]
    assert payload["parsed_summary"]["peer_configured"] is True
    assert payload["local_ip_hash"] == hashlib.sha256(
        local_ip.encode("utf-8")
    ).hexdigest()
    assert payload["remote_ip_hash"] == hashlib.sha256(
        remote_ip.encode("utf-8")
    ).hexdigest()
    assert payload["stderr_metadata"]["sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    text = str(payload)
    assert "secret-tun1" not in text
    assert local_ip not in text
    assert remote_ip not in text
    assert stderr not in text


@pytest.mark.asyncio
async def test_set_address_missing_ip_command_publishes_redacted_failure(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    tun = mod.TUNInterface("secret-tun2", event_bus=bus)
    local_ip = "10.88.0.1/32"

    def _missing(*args, **kwargs):
        raise FileNotFoundError("ip")

    monkeypatch.setattr(mod.subprocess, "run", _missing)

    assert await tun.set_address(local_ip) is False
    payload = _stage_payload(bus, "tun_interface_address_command_missing")

    assert payload["returncode"] == 127
    assert payload["error"]["type"] == "FileNotFoundError"
    assert payload["error"]["message_redacted"] is True
    assert payload["parsed_summary"]["command_available"] is False
    assert local_ip not in str(payload)


@pytest.mark.asyncio
async def test_set_address_timeout_publishes_redacted_failure(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    tun = mod.TUNInterface("secret-tun3", event_bus=bus)
    local_ip = "10.99.0.1/32"

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=["ip", "addr", "add", local_ip],
            timeout=5,
            output="secret timeout stdout",
            stderr="secret timeout stderr",
        )

    monkeypatch.setattr(mod.subprocess, "run", _timeout)

    assert await tun.set_address(local_ip) is False
    payload = _stage_payload(bus, "tun_interface_address_timeout")

    assert payload["returncode"] == 124
    assert payload["error"]["type"] == "TimeoutExpired"
    assert payload["stdout_metadata"]["sha256"] == hashlib.sha256(
        b"secret timeout stdout"
    ).hexdigest()
    assert payload["stderr_metadata"]["sha256"] == hashlib.sha256(
        b"secret timeout stderr"
    ).hexdigest()
    text = str(payload)
    assert local_ip not in text
    assert "secret timeout stdout" not in text
    assert "secret timeout stderr" not in text
