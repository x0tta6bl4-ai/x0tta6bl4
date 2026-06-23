import importlib
import json
import os

import pytest

from src.coordination.events import EventBus, EventType
from src.services.service_event_trace import service_event_trace_history

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


class _FakeProcess:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout.encode() if isinstance(stdout, str) else stdout
        self.stderr = stderr.encode() if isinstance(stderr, str) else stderr
        self.returncode = returncode
        self.input = None
        self.terminated = False

    async def communicate(self, input=None):
        self.input = input
        return self.stdout, self.stderr

    def terminate(self):
        self.terminated = True
        self.returncode = -15


def _fake_exec_sequence(processes, calls):
    async def _fake_exec(*args, **kwargs):
        assert "timeout" not in kwargs
        calls.append((args, kwargs))
        return processes.pop(0)

    return _fake_exec


def _latest_real_network_event(bus):
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent="real-network-adapter",
        limit=20,
    )
    assert events
    return events[-1]


def test_import_smoke():
    try:
        mod = importlib.import_module("src.mesh.real_network_adapter")
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None


def test_yggdrasil_peer_metric_estimate_marks_derived_values():
    mod = importlib.import_module("src.mesh.real_network_adapter")

    metrics = mod.estimate_yggdrasil_peer_metrics(
        {
            "address": "200:dead:beef::1",
            "coords": [1, 2, 3],
            "bytes_sent": 1024 * 1024,
            "bytes_recvd": 1024 * 1024,
            "uptime": 2,
        }
    )
    metric_text = str(metrics)

    assert metrics["latency_ms"] == pytest.approx(20.0)
    assert metrics["bandwidth_mbps"] == pytest.approx(8.0)
    assert metrics["sources"]["latency_ms"] == {
        "source": "admin_estimate",
        "field": "coords",
    }
    assert metrics["sources"]["bandwidth_mbps"] == {
        "source": "admin_estimate",
        "field": "bytes_sent+bytes_recvd/uptime",
    }
    assert metrics["basis"]["values_redacted"] is True
    assert "200:dead:beef" not in metric_text


@pytest.mark.asyncio
async def test_dataplane_ping_probe_publishes_redacted_rtt_loss(
    monkeypatch,
    tmp_path,
):
    mod = importlib.import_module("src.mesh.real_network_adapter")
    bus = EventBus(project_root=str(tmp_path))
    calls = []
    raw_target = "200:dead:beef::1"
    stdout = (
        "2 packets transmitted, 2 received, 0% packet loss, time 1001ms\n"
        "rtt min/avg/max/mdev = 10.0/12.5/15.0/2.5 ms\n"
    )
    monkeypatch.setattr(
        mod.asyncio,
        "create_subprocess_exec",
        _fake_exec_sequence([_FakeProcess(stdout=stdout)], calls),
    )

    metrics = await mod.probe_peer_dataplane_ping(raw_target, event_bus=bus)
    event = _latest_real_network_event(bus)
    data = event.data
    event_text = str(data)

    assert metrics["status"] == "ok"
    assert metrics["latency_ms"] == pytest.approx(12.5)
    assert metrics["packet_loss_percent"] == pytest.approx(0.0)
    assert metrics["jitter_ms"] == pytest.approx(2.5)
    assert metrics["sources"]["latency_ms"] == {
        "source": "dataplane_probe",
        "field": "ping_avg_rtt_ms",
    }
    assert calls[0][0] == ("ping", "-c", "2", "-W", "1", "-q", raw_target)
    assert data["operation"] == "dataplane_ping_probe"
    assert data["resource"] == "mesh:dataplane:ping_probe"
    assert data["command"] == ["ping", "-c", "2", "-W", "1", "-q", "[redacted]"]
    assert data["target"]["kind"] == "dataplane_ping_target"
    assert data["parsed_summary"]["latency_ms"] == pytest.approx(12.5)
    assert data["parsed_summary"]["packet_loss_percent"] == pytest.approx(0.0)
    assert data["output"]["stdout_sha256"]
    assert raw_target not in event_text


@pytest.mark.asyncio
async def test_batman_originators_publish_bounded_observed_state(monkeypatch, tmp_path):
    mod = importlib.import_module("src.mesh.real_network_adapter")
    bus = EventBus(project_root=str(tmp_path))
    calls = []
    raw_mac = "aa:bb:cc:dd:ee:ff"
    raw_nexthop = "11:22:33:44:55:66"
    stdout = (
        "B.A.T.M.A.N. adv openwrt-2021.0\n"
        "Originator      last-seen (#/255) Nexthop           [outgoingIF]\n"
        f"{raw_mac}    0.020s   (255) {raw_nexthop} [wlan0]\n"
    )
    monkeypatch.setattr(
        mod.asyncio,
        "create_subprocess_exec",
        _fake_exec_sequence([_FakeProcess(stdout=stdout)], calls),
    )

    adapter = mod.BatmanAdvAdapter(event_bus=bus)
    originators = await adapter.get_originators()
    event = _latest_real_network_event(bus)
    data = event.data
    event_text = str(data)

    assert originators[0]["mac"] == raw_mac
    assert originators[0]["nexthop"] == raw_nexthop
    assert calls[0][0] == ("batctl", "o")
    assert data["resource"] == "mesh:batman_adv:originators"
    assert data["operation"] == "batman_originators"
    assert data["service_name"] == "real-network-adapter"
    assert data["layer"] == "mesh_real_network_observed_state"
    assert data["read_only"] is True
    assert data["observed_state"] is True
    assert data["safe_actuator"] is False
    assert data["source_mode"] == "real_command"
    assert data["returncode"] == 0
    assert data["identity"]["redacted"] is True
    assert data["parsed_summary"]["originator_count"] == 1
    assert data["output"]["output_redacted"] is True
    assert data["output"]["stdout_chars"] > 0
    assert data["output"]["stdout_sha256"]
    assert raw_mac not in event_text
    assert raw_nexthop not in event_text


@pytest.mark.asyncio
async def test_batman_throughput_redacts_target_and_has_no_exec_timeout_kwarg(
    monkeypatch,
    tmp_path,
):
    mod = importlib.import_module("src.mesh.real_network_adapter")
    bus = EventBus(project_root=str(tmp_path))
    calls = []
    raw_mac = "aa:bb:cc:dd:ee:ff"
    originators_stdout = (
        "B.A.T.M.A.N. adv openwrt-2021.0\n"
        "Originator      last-seen (#/255) Nexthop           [outgoingIF]\n"
        f"{raw_mac}    0.020s   (255) 11:22:33:44:55:66 [wlan0]\n"
    )
    throughput_stdout = "Throughput: 12.34 Mbits/sec\n"
    monkeypatch.setattr(
        mod.asyncio,
        "create_subprocess_exec",
        _fake_exec_sequence(
            [
                _FakeProcess(stdout=originators_stdout),
                _FakeProcess(stdout=throughput_stdout),
            ],
            calls,
        ),
    )

    adapter = mod.BatmanAdvAdapter(event_bus=bus)
    throughput = await adapter.get_throughput()
    event = _latest_real_network_event(bus)
    data = event.data
    event_text = str(data)

    assert throughput == {raw_mac: 12.34}
    assert calls[-1][0] == ("batctl", "tp", "-m", raw_mac)
    assert data["resource"] == "mesh:batman_adv:throughput"
    assert data["operation"] == "batman_throughput"
    assert data["command"] == ["batctl", "tp", "-m", "[redacted]"]
    assert data["target"]["kind"] == "batman_originator_mac"
    assert data["target"]["redacted"] is True
    assert data["target"]["sha256"]
    assert data["parsed_summary"] == {
        "measurement_found": True,
        "throughput_mbps": 12.34,
    }
    assert raw_mac not in event_text


@pytest.mark.asyncio
async def test_yggdrasil_admin_request_publish_bounded_observed_state(
    monkeypatch,
    tmp_path,
):
    mod = importlib.import_module("src.mesh.real_network_adapter")
    bus = EventBus(project_root=str(tmp_path))
    calls = []
    raw_peer = "200:dead:beef::1"
    response = {
        "response": {
            "peers": {
                raw_peer: {
                    "port": 1234,
                    "coords": [1, 2, 3],
                    "bytes_sent": 10,
                    "bytes_recvd": 20,
                    "uptime": 5,
                }
            }
        }
    }
    monkeypatch.setattr(
        mod.asyncio,
        "create_subprocess_exec",
        _fake_exec_sequence([_FakeProcess(stdout=json.dumps(response))], calls),
    )

    adapter = mod.YggdrasilAdapter(event_bus=bus)
    peers = await adapter.get_peers()
    event = _latest_real_network_event(bus)
    data = event.data
    event_text = str(data)

    assert peers[0]["address"] == raw_peer
    assert calls[0][0] == ("yggdrasilctl", "-json", "-v")
    assert data["resource"] == "mesh:yggdrasil:admin_api"
    assert data["operation"] == "yggdrasil_admin_request"
    assert data["request"] == {
        "type": "getPeers",
        "type_redacted": False,
        "payload_redacted": True,
    }
    assert data["parsed_summary"] == {
        "request_type": "getPeers",
        "request_type_redacted": False,
        "peer_count": 1,
    }
    assert data["output"]["stdout_sha256"]
    assert raw_peer not in event_text


@pytest.mark.asyncio
async def test_real_network_failure_event_redacts_stderr(monkeypatch, tmp_path):
    mod = importlib.import_module("src.mesh.real_network_adapter")
    bus = EventBus(project_root=str(tmp_path))
    raw_error = "batctl failed for aa:bb:cc:dd:ee:ff via 10.0.0.1"
    monkeypatch.setattr(
        mod.asyncio,
        "create_subprocess_exec",
        _fake_exec_sequence([_FakeProcess(stderr=raw_error, returncode=7)], []),
    )

    adapter = mod.BatmanAdvAdapter(event_bus=bus)
    originators = await adapter.get_originators()
    event = _latest_real_network_event(bus)
    data = event.data
    event_text = str(data)

    assert originators == []
    assert data["status"] == "failed"
    assert data["returncode"] == 7
    assert data["output"]["stderr_chars"] == len(raw_error)
    assert data["output"]["stderr_sha256"]
    assert "aa:bb:cc:dd:ee:ff" not in event_text
    assert "10.0.0.1" not in event_text
    assert "batctl failed for" not in event_text


@pytest.mark.asyncio
async def test_real_network_observed_state_trace_is_registered(monkeypatch, tmp_path):
    mod = importlib.import_module("src.mesh.real_network_adapter")
    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(
        mod.asyncio,
        "create_subprocess_exec",
        _fake_exec_sequence(
            [
                _FakeProcess(
                    stdout=(
                        "B.A.T.M.A.N. adv openwrt-2021.0\n"
                        "Originator      last-seen (#/255) Nexthop [outgoingIF]\n"
                    )
                )
            ],
            [],
        ),
    )

    adapter = mod.BatmanAdvAdapter(event_bus=bus)
    assert await adapter.get_originators() == []

    trace = service_event_trace_history(
        bus,
        service_name="real-network-adapter",
        event_type=EventType.PIPELINE_STAGE_END,
        limit=10,
    )

    assert trace["events_total"] == 1
    assert trace["filter"]["services"][0]["layer"] == (
        "mesh_real_network_observed_state"
    )
    assert trace["events"][0]["source_agent"] == "real-network-adapter"
