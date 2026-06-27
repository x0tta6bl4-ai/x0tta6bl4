import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.loader import EBPFAttachMode, EBPFLoader, EBPFProgramType


def _loader(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    loader = EBPFLoader(programs_dir=tmp_path, event_bus=bus)
    return loader, bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-legacy-loader",
        limit=20,
    )


def _assert_thinking_context(payload):
    thinking = payload["thinking"]
    techniques = set(thinking["techniques"])
    assert thinking["role"] == "security"
    assert "stride_threat_modeling" in techniques
    assert "zero_trust_review" in techniques
    assert "mape_k" in techniques
    assert "causal_analysis" in techniques
    assert "reverse_planning" in techniques
    assert thinking["applied"]["framing"]["problem"] == (
        "ebpf_legacy_loader_operation"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["stage"] == payload["stage"]
    assert constraints["output_redacted"] is True
    assert "extra_keys" in constraints


def test_bpftool_load_success_publishes_redacted_evidence(tmp_path):
    loader, bus = _loader(tmp_path)
    program_path = tmp_path / "secret_xdp_prog.o"
    program_path.write_bytes(b"\x7fELF")
    load_stdout = "secret load output"
    which_result = SimpleNamespace(returncode=0, stdout="/usr/bin/bpftool", stderr="")
    load_result = SimpleNamespace(returncode=0, stdout=load_stdout, stderr="")

    with patch(
        "src.network.ebpf.loader.safe_run",
        side_effect=[which_result, load_result],
    ):
        with patch.object(Path, "mkdir"):
            fd, pinned_path = loader._load_via_bpftool(
                program_path,
                EBPFProgramType.XDP,
            )

    assert fd is None
    assert pinned_path is not None
    payload = _events(bus)[-1].data
    assert payload["stage"] == "legacy_loader_bpftool_load_succeeded"
    assert payload["operation"] == "bpftool_prog_load"
    assert payload["read_only"] is False
    assert payload["returncode"] == 0
    assert payload["program_path_hash"] == hashlib.sha256(
        str(program_path).encode("utf-8")
    ).hexdigest()
    assert payload["bpffs_path_redacted"] is True
    assert payload["command"] == [
        "bpftool",
        "prog",
        "load",
        "[redacted]",
        "[redacted]",
    ]
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        load_stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert str(program_path) not in str(payload)
    assert pinned_path not in str(payload)
    assert load_stdout not in str(payload)


def test_bpftool_verify_attachment_publishes_redacted_evidence(
    tmp_path, monkeypatch
):
    loader, bus = _loader(tmp_path)
    interface = "secret0"
    stdout = "987654: xdp id 987654 tag secret-tag"

    monkeypatch.setattr(
        "src.network.ebpf.loader.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert loader._verify_attachment(987654, interface, EBPFProgramType.XDP) is True
    payload = _events(bus)[-1].data
    assert payload["stage"] == "legacy_loader_bpftool_verify_attachment_succeeded"
    assert payload["operation"] == "bpftool_verify_attachment"
    assert payload["command"] == ["bpftool", "prog", "show", "id", "[redacted]"]
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert stdout not in str(payload)


def test_get_stats_publishes_redacted_map_read_evidence(tmp_path, monkeypatch):
    loader, bus = _loader(tmp_path)
    stdout = json.dumps(
        [
            {"key": 0, "value": 1000, "note": "secret stats payload"},
            {"key": 1, "value": 800},
            {"key": 2, "value": 150},
            {"key": 3, "value": 50},
        ]
    )

    monkeypatch.setattr(
        "src.network.ebpf.loader.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    stats = loader.get_stats()

    assert stats["total_packets"] == 1000
    payload = _events(bus)[-1].data
    assert payload["stage"] == "legacy_loader_stats_map_read_succeeded"
    assert payload["operation"] == "bpftool_map_dump_stats"
    assert payload["map_name_hash"] == hashlib.sha256(b"packet_stats").hexdigest()
    assert payload["parsed_summary"]["parsed_entries"] == 4
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert "packet_stats" not in str(payload)
    assert "secret stats payload" not in str(payload)


def test_update_routes_publishes_redacted_route_update_evidence(
    tmp_path, monkeypatch
):
    loader, bus = _loader(tmp_path)
    dest_ip = "10.10.10.10"
    next_hop = "secret-next-hop"
    stdout = "secret route update"

    monkeypatch.setattr(
        "src.network.ebpf.loader.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert loader.update_routes({dest_ip: next_hop}) is True
    payload = _events(bus)[-1].data
    assert payload["stage"] == "legacy_loader_route_update_succeeded"
    assert payload["operation"] == "bpftool_map_update_routes"
    assert payload["read_only"] is False
    assert payload["command"] == [
        "bpftool",
        "map",
        "update",
        "name",
        "mesh_routes",
        "key",
        "[redacted]",
        "value",
        "[redacted]",
    ]
    assert payload["dest_ip_hash"] == hashlib.sha256(
        dest_ip.encode("utf-8")
    ).hexdigest()
    assert payload["next_hop_if_hash"] == hashlib.sha256(
        next_hop.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert dest_ip not in str(payload)
    assert next_hop not in str(payload)
    assert stdout not in str(payload)


def test_xdp_program_attach_publishes_redacted_ip_link_evidence(
    tmp_path, monkeypatch
):
    loader, bus = _loader(tmp_path)
    interface = "secret1"
    program_source = str(tmp_path / "secret_prog.o")
    stdout = "secret attach output"

    monkeypatch.setattr(loader, "_try_bpftool_attach", lambda *_args: False)
    monkeypatch.setattr(
        "src.network.ebpf.loader.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert (
        loader._attach_xdp_program(
            interface,
            program_source,
            None,
            EBPFAttachMode.SKB,
        )
        is True
    )
    payload = _events(bus)[-1].data
    assert payload["stage"] == "legacy_loader_xdp_program_attach_succeeded"
    assert payload["operation"] == "xdp_program_attach"
    assert payload["command"][4] == "[redacted]"
    assert payload["command"][7] == "[redacted]"
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["program_source_hash"] == hashlib.sha256(
        program_source.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert program_source not in str(payload)
    assert stdout not in str(payload)
