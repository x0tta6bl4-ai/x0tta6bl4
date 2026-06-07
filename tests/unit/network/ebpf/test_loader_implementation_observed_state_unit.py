import hashlib
import subprocess
from types import SimpleNamespace

from src.coordination.events import EventBus, EventType
from src.network.ebpf import loader_implementation as loader_impl
from src.network.ebpf.loader_implementation import EBPFLoaderImplementation


def _loader(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    loader = EBPFLoaderImplementation(programs_dir=tmp_path, event_bus=bus)
    return loader, bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-loader-implementation",
        limit=20,
    )


def _assert_thinking_context(payload):
    thinking = payload["thinking"]
    techniques = set(thinking["techniques"])
    assert thinking["role"] == "security"
    assert "zero_trust_review" in techniques
    assert "stride_threat_modeling" in techniques
    assert "mape_k" in techniques
    assert "reverse_planning" in techniques
    assert "chaos_driven_design" in techniques
    assert thinking["applied"]["framing"]["problem"] == (
        "ebpf_loader_implementation_operation"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["command_shape"] == payload["command"]


def test_detach_verify_ip_link_failure_publishes_redacted_evidence(
    tmp_path, monkeypatch
):
    loader, bus = _loader(tmp_path)
    program_id = "secret-program-id"
    interface = "secret0"
    stderr = "secret missing device"
    loader.loaded_programs[program_id] = {"attached_to": interface}

    def fake_run(cmd, capture_output, text, timeout):
        assert cmd == ["ip", "link", "show", "dev", interface]
        return SimpleNamespace(returncode=1, stdout="", stderr=stderr)

    monkeypatch.setattr(loader_impl.subprocess, "run", fake_run)

    assert loader._verify_program_detached(program_id) is False
    payload = _events(bus)[-1].data
    assert payload["stage"] == "ebpf_loader_detach_verify_failed"
    assert payload["operation"] == "verify_program_detached"
    assert payload["status"] == "failure"
    assert payload["returncode"] == 1
    assert payload["program_id_hash"] == hashlib.sha256(
        program_id.encode("utf-8")
    ).hexdigest()
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stderr_sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    assert payload["command"] == ["ip", "link", "show", "dev", "[redacted]"]
    assert payload["identity"]["redacted"] is True
    _assert_thinking_context(payload)
    assert program_id not in str(payload)
    assert interface not in str(payload)
    assert stderr not in str(payload)


def test_detach_verify_xdp_attached_publishes_redacted_evidence(
    tmp_path, monkeypatch
):
    loader, bus = _loader(tmp_path)
    program_id = "secret-attached-program"
    interface = "secret1"
    stdout = "2: secret1: <BROADCAST,MULTICAST,UP>\n    xdp id 42"
    loader.loaded_programs[program_id] = {"attached_to": interface}

    monkeypatch.setattr(
        loader_impl.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert loader._verify_program_detached(program_id) is False
    payload = _events(bus)[-1].data
    assert payload["stage"] == "ebpf_loader_detach_verify_attached"
    assert payload["status"] == "failure"
    assert payload["parsed_summary"]["detached"] is False
    assert payload["parsed_summary"]["attachment_detected"] is True
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert program_id not in str(payload)
    assert interface not in str(payload)
    assert stdout not in str(payload)


def test_verify_program_loaded_success_publishes_redacted_bpftool_evidence(
    tmp_path, monkeypatch
):
    loader, bus = _loader(tmp_path)
    program_id = "secret-loaded-program"
    program_path = tmp_path / "secret_xdp_program.o"
    stdout = f"42: xdp name {program_path.name} tag abc"
    loader.loaded_programs[program_id] = {"path": str(program_path)}

    monkeypatch.setattr(
        loader_impl.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert loader.verify_program_loaded(program_id) is True
    payload = _events(bus)[-1].data
    assert payload["stage"] == "ebpf_loader_program_loaded_verified"
    assert payload["operation"] == "verify_program_loaded"
    assert payload["status"] == "success"
    assert payload["parsed_summary"]["program_seen"] is True
    assert payload["program_id_hash"] == hashlib.sha256(
        program_id.encode("utf-8")
    ).hexdigest()
    assert payload["program_path_hash"] == hashlib.sha256(
        str(program_path).encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert program_id not in str(payload)
    assert str(program_path) not in str(payload)
    assert stdout not in str(payload)


def test_verify_program_loaded_timeout_publishes_redacted_error(tmp_path, monkeypatch):
    loader, bus = _loader(tmp_path)
    program_id = "secret-timeout-program"
    program_path = tmp_path / "secret_timeout_program.o"
    loader.loaded_programs[program_id] = {"path": str(program_path)}

    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(loader_impl.subprocess, "run", fake_run)

    assert loader.verify_program_loaded(program_id) is True
    payload = _events(bus)[-1].data
    assert payload["stage"] == "ebpf_loader_program_loaded_verify_error"
    assert payload["status"] == "failure"
    assert payload["error"]["type"] == "TimeoutExpired"
    assert payload["error"]["message_redacted"] is True
    assert program_id not in str(payload)
    assert str(program_path) not in str(payload)


def test_get_program_stats_success_publishes_redacted_bpftool_evidence(
    tmp_path, monkeypatch
):
    loader, bus = _loader(tmp_path)
    program_id = "secret-stats-program"
    program_path = tmp_path / "secret_stats_program.o"
    interface = "secret2"
    pinned_path = tmp_path / "secret_pinned"
    stdout = "secret kernel stats"
    loader.loaded_programs[program_id] = {
        "path": str(program_path),
        "attached_to": interface,
        "pinned_path": str(pinned_path),
    }

    monkeypatch.setattr(
        loader_impl.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    stats = loader.get_program_stats(program_id)

    assert stats["kernel_info"] == stdout
    payload = _events(bus)[-1].data
    assert payload["stage"] == "ebpf_loader_program_stats_observed"
    assert payload["operation"] == "get_program_stats"
    assert payload["returncode"] == 0
    assert payload["command"] == ["bpftool", "prog", "show", "id", "[redacted]"]
    assert payload["program_id_hash"] == hashlib.sha256(
        program_id.encode("utf-8")
    ).hexdigest()
    assert payload["attached_to_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["pinned_path_hash"] == hashlib.sha256(
        str(pinned_path).encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert program_id not in str(payload)
    assert str(program_path) not in str(payload)
    assert interface not in str(payload)
    assert str(pinned_path) not in str(payload)
    assert stdout not in str(payload)
