import subprocess

from src.coordination.events import EventBus, EventType
from src.network import yggdrasil_client


class FakeCompleted:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def fake_run_status(*args, **kwargs):
    return FakeCompleted(
        "Public key: TESTKEY\nIPv6 address: 200:dead:beef::1\nRouting table size: 3\n"
    )


def fake_run_peers(*args, **kwargs):
    return FakeCompleted(
        "Peer  Port  Protocol  Remote Address\n1  tcp  10.0.0.1\n2  tcp  10.0.0.2\n"
    )


def fake_run_peers_fatal_zero(*args, **kwargs):
    return FakeCompleted(
        "",
        (
            "Fatal error: dial unix /var/run/yggdrasil/yggdrasil.sock: "
            "connect: no such file or directory"
        ),
        0,
    )


def test_get_yggdrasil_status(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(subprocess, "run", fake_run_status)
    status = yggdrasil_client.get_yggdrasil_status(event_bus=bus)
    assert status["status"] == "online"
    assert status["node"]["public_key"] == "TESTKEY"
    assert status["node"]["ipv6_address"].startswith("200:dead:beef")


def test_get_yggdrasil_peers(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(subprocess, "run", fake_run_peers)
    peers = yggdrasil_client.get_yggdrasil_peers(event_bus=bus)
    assert peers["status"] == "ok"
    assert peers["count"] == 2
    assert all("remote" in p for p in peers["peers"])


def test_get_yggdrasil_routes(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(subprocess, "run", fake_run_status)
    routes = yggdrasil_client.get_yggdrasil_routes(event_bus=bus)
    assert routes["status"] == "ok"
    assert routes["routing_table_size"] == 3


def _latest_yggdrasil_event(bus: EventBus):
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent="yggdrasil-client",
        limit=10,
    )
    assert events
    return events[-1]


def test_yggdrasil_status_publishes_bounded_observed_state(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(
        yggdrasil_client,
        "_find_yggdrasilctl",
        lambda: "/usr/local/bin/yggdrasilctl",
    )
    monkeypatch.setattr(subprocess, "run", fake_run_status)

    status = yggdrasil_client.get_yggdrasil_status(event_bus=bus)
    event = _latest_yggdrasil_event(bus)
    data = event.data
    event_text = str(data)

    assert status["node"]["public_key"] == "TESTKEY"
    assert data["resource"] == "network:yggdrasil:get_self"
    assert data["operation"] == "get_self"
    assert data["service_name"] == "yggdrasil-client"
    assert data["layer"] == "network_yggdrasil_observed_state"
    assert data["read_only"] is True
    assert data["observed_state"] is True
    assert data["safe_actuator"] is False
    assert data["source_mode"] == "real_command"
    assert data["returncode"] == 0
    assert data["return_code"] == 0
    assert data["duration_ms"] >= 0
    assert data["identity"]["service_name"] == "yggdrasil-client"
    assert data["identity"]["redacted"] is True
    assert data["service_identity"] == data["identity"]
    assert data["raw_values_redacted"] is True
    assert data["payloads_redacted"] is True
    assert data["output"]["output_redacted"] is True
    assert data["output"]["stdout_chars"] > 0
    assert data["output"]["stdout_sha256"]
    assert data["claim_gate"] == {
        "schema": "x0tta6bl4.yggdrasil_observed_state.claim_gate.v1",
        "decision": "LOCAL_YGGDRASIL_OBSERVED_STATE_ONLY",
        "local_observed_state_claim_allowed": True,
        "real_yggdrasil_daemon_observed": True,
        "mock_source_mode": False,
        "return_code_observed": True,
        "remote_peer_authenticity_claim_allowed": False,
        "route_quality_claim_allowed": False,
        "live_packet_reachability_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blockers": [],
        "claim_boundary": (
            yggdrasil_client.YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY
        ),
        "redacted": True,
    }
    assert "TESTKEY" not in event_text
    assert "200:dead:beef" not in event_text


def test_yggdrasil_status_can_attach_evidence_event_id(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(
        yggdrasil_client,
        "_find_yggdrasilctl",
        lambda: "/usr/local/bin/yggdrasilctl",
    )
    monkeypatch.setattr(subprocess, "run", fake_run_status)

    status = yggdrasil_client.get_yggdrasil_status(
        event_bus=bus,
        include_evidence=True,
    )
    event = _latest_yggdrasil_event(bus)

    assert status["status"] == "online"
    assert status["evidence"] == {
        "source_agents": ["yggdrasil-client"],
        "layer": "network_yggdrasil_observed_state",
        "event_ids": [event.event_id],
        "events_total": 1,
        "event_ids_limit": 1,
        "event_ids_truncated": False,
        "payloads_redacted": True,
        "redacted": True,
        "claim_boundary": yggdrasil_client.YGGDRASIL_OBSERVED_STATE_CLAIM_BOUNDARY,
    }


def test_yggdrasil_peers_publishes_bounded_observed_state(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(
        yggdrasil_client,
        "_find_yggdrasilctl",
        lambda: "/usr/local/bin/yggdrasilctl",
    )
    monkeypatch.setattr(subprocess, "run", fake_run_peers)

    peers = yggdrasil_client.get_yggdrasil_peers(event_bus=bus)
    event = _latest_yggdrasil_event(bus)
    data = event.data
    event_text = str(data)

    assert peers["count"] == 2
    assert data["resource"] == "network:yggdrasil:get_peers"
    assert data["operation"] == "get_peers"
    assert data["command"] == ["yggdrasilctl", "getPeers"]
    assert data["parsed_summary"] == {
        "status": "ok",
        "peer_count": 2,
        "protocols": ["tcp"],
    }
    assert data["claim_gate"]["local_observed_state_claim_allowed"] is True
    assert data["claim_gate"]["remote_peer_authenticity_claim_allowed"] is False
    assert data["claim_gate"]["live_packet_reachability_claim_allowed"] is False
    assert data["claim_gate"]["production_readiness_claim_allowed"] is False
    assert data["output"]["stdout_chars"] > 0
    assert data["output"]["stdout_sha256"]
    assert "10.0.0.1" not in event_text
    assert "10.0.0.2" not in event_text


def test_yggdrasil_peers_fatal_output_is_failed_even_with_zero_returncode(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(
        yggdrasil_client,
        "_find_yggdrasilctl",
        lambda: "/usr/local/bin/yggdrasilctl",
    )
    monkeypatch.setattr(subprocess, "run", fake_run_peers_fatal_zero)

    peers = yggdrasil_client.get_yggdrasil_peers(event_bus=bus)
    event = _latest_yggdrasil_event(bus)
    data = event.data
    event_text = str(data)

    assert peers["status"] == "error"
    assert peers["count"] == 0
    assert peers["error"] == "yggdrasilctl reported fatal error"
    assert data["status"] == "failed"
    assert data["returncode"] == 0
    assert data["return_code"] == 0
    assert data["parsed_summary"] == {"status": "failed", "output_failure": True}
    assert data["claim_gate"]["decision"] == "YGGDRASIL_OBSERVED_STATE_UNPROVEN"
    assert (
        data["claim_gate"]["local_observed_state_claim_allowed"] is False
    )
    assert "yggdrasil_observed_state_not_confirmed" in (
        data["claim_gate"]["blockers"]
    )
    assert data["error"] == {
        "type": "YggdrasilCommandOutputError",
        "message_redacted": True,
    }
    assert data["output"]["stderr_chars"] > 0
    assert data["output"]["stderr_sha256"]
    assert "Fatal error" not in event_text
    assert "yggdrasil.sock" not in event_text


def test_yggdrasil_routes_publishes_bounded_observed_state(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(
        yggdrasil_client,
        "_find_yggdrasilctl",
        lambda: "/usr/local/bin/yggdrasilctl",
    )
    monkeypatch.setattr(subprocess, "run", fake_run_status)

    routes = yggdrasil_client.get_yggdrasil_routes(event_bus=bus)
    event = _latest_yggdrasil_event(bus)
    data = event.data

    assert routes["routing_table_size"] == 3
    assert data["resource"] == "network:yggdrasil:get_routes"
    assert data["operation"] == "get_routes"
    assert data["returncode"] == 0
    assert data["parsed_summary"]["routing_table_size"] == 3
    assert data["output"]["output_bounded"] is True


def test_yggdrasil_peer_error_publishes_failed_observed_state(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(
        yggdrasil_client,
        "_find_yggdrasilctl",
        lambda: "/usr/local/bin/yggdrasilctl",
    )

    def _run(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            returncode=7,
            cmd="yggdrasilctl getPeers",
            output="Peer  Port  Protocol  Remote Address\n1 tcp 10.0.0.1\n",
            stderr="raw peer failure detail 10.0.0.2",
        )

    monkeypatch.setattr(subprocess, "run", _run)

    peers = yggdrasil_client.get_yggdrasil_peers(event_bus=bus)
    event = _latest_yggdrasil_event(bus)
    data = event.data
    event_text = str(data)

    assert peers["status"] == "error"
    assert data["status"] == "failed"
    assert data["returncode"] == 7
    assert data["error"] == {
        "type": "CalledProcessError",
        "message_redacted": True,
    }
    assert data["output"]["stdout_chars"] > 0
    assert data["output"]["stderr_chars"] > 0
    assert "10.0.0.1" not in event_text
    assert "10.0.0.2" not in event_text
    assert "raw peer failure detail" not in event_text


def test_yggdrasil_mock_status_publishes_source_mode(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setenv("YGGDRASIL_MOCK", "1")

    status = yggdrasil_client.get_yggdrasil_status(event_bus=bus)
    event = _latest_yggdrasil_event(bus)
    data = event.data

    assert status["status"] == "mock"
    assert data["source_mode"] == "mock"
    assert data["status"] == "mock"
    assert data["returncode"] == 0
    assert data["return_code"] == 0
    assert data["claim_gate"]["mock_source_mode"] is True
    assert data["claim_gate"]["real_yggdrasil_daemon_observed"] is False
    assert "mock_source_mode_not_live_mesh_evidence" in data["claim_gate"][
        "blockers"
    ]
