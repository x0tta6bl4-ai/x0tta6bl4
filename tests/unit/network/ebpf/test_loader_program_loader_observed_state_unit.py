import hashlib
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.loader.program_loader import EBPFProgramLoader, EBPFProgramType


def _loader(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    loader = EBPFProgramLoader(programs_dir=tmp_path, event_bus=bus)
    return loader, bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-loader-program-loader",
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
        "ebpf_loader_program_observation"
    )
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["command_shape"] == payload["command"]


def test_bpftool_load_success_publishes_redacted_evidence(tmp_path):
    loader, bus = _loader(tmp_path)
    program_path = tmp_path / "secret_prog.o"
    program_path.write_bytes(b"\x7fELF")
    load_stdout = "secret load stdout"
    which_result = SimpleNamespace(returncode=0, stdout="/usr/bin/bpftool", stderr="")
    load_result = SimpleNamespace(returncode=0, stdout=load_stdout, stderr="")

    with patch(
        "src.network.ebpf.loader.program_loader.safe_run",
        side_effect=[which_result, load_result],
    ):
        with patch.object(Path, "mkdir"):
            fd, pinned_path = loader.load_via_bpftool(
                program_path,
                EBPFProgramType.XDP,
            )

    assert fd is None
    assert pinned_path is not None
    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_program_loader_bpftool_load_succeeded"
    assert payload["operation"] == "bpftool_prog_load"
    assert payload["read_only"] is False
    assert payload["returncode"] == 0
    assert payload["command"] == [
        "bpftool",
        "prog",
        "load",
        "[redacted]",
        "[redacted]",
    ]
    assert payload["program_path_hash"] == hashlib.sha256(
        str(program_path).encode("utf-8")
    ).hexdigest()
    assert payload["bpffs_path_redacted"] is True
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        load_stdout.encode("utf-8")
    ).hexdigest()
    assert payload["identity"]["redacted"] is True
    _assert_thinking_context(payload)
    assert str(program_path) not in str(payload)
    assert pinned_path not in str(payload)
    assert load_stdout not in str(payload)


def test_bpftool_load_failure_publishes_redacted_failure_evidence(tmp_path):
    loader, bus = _loader(tmp_path)
    program_path = tmp_path / "secret_failed_prog.o"
    program_path.write_bytes(b"\x7fELF")
    stderr = "secret verifier failure"
    which_result = SimpleNamespace(returncode=0, stdout="/usr/bin/bpftool", stderr="")
    load_result = SimpleNamespace(returncode=2, stdout="", stderr=stderr)

    with patch(
        "src.network.ebpf.loader.program_loader.safe_run",
        side_effect=[which_result, load_result],
    ):
        with patch.object(Path, "mkdir"):
            assert loader.load_via_bpftool(program_path, EBPFProgramType.XDP) == (
                None,
                None,
            )

    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_program_loader_bpftool_load_failed"
    assert payload["status"] == "failure"
    assert payload["returncode"] == 2
    assert payload["program_path_hash"] == hashlib.sha256(
        str(program_path).encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stderr_sha256"] == hashlib.sha256(
        stderr.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert str(program_path) not in str(payload)
    assert stderr not in str(payload)


def test_bpftool_unavailable_publishes_redacted_empty_evidence(tmp_path):
    loader, bus = _loader(tmp_path)
    program_path = tmp_path / "secret_missing_bpftool.o"
    which_result = SimpleNamespace(returncode=1, stdout="", stderr="secret missing")

    with patch(
        "src.network.ebpf.loader.program_loader.safe_run",
        return_value=which_result,
    ):
        assert loader.load_via_bpftool(program_path, EBPFProgramType.XDP) == (
            None,
            None,
        )

    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_program_loader_bpftool_unavailable"
    assert payload["operation"] == "bpftool_available"
    assert payload["status"] == "empty"
    assert payload["command"] == ["which", "bpftool"]
    assert payload["program_path_hash"] == hashlib.sha256(
        str(program_path).encode("utf-8")
    ).hexdigest()
    assert str(program_path) not in str(payload)
    assert "secret missing" not in str(payload)


def test_bpftool_load_timeout_publishes_redacted_error_evidence(tmp_path):
    loader, bus = _loader(tmp_path)
    program_path = tmp_path / "secret_timeout_prog.o"
    program_path.write_bytes(b"\x7fELF")
    which_result = SimpleNamespace(returncode=0, stdout="/usr/bin/bpftool", stderr="")
    timeout = subprocess.TimeoutExpired(
        cmd="bpftool",
        timeout=10,
        output="secret timeout output",
        stderr="secret timeout stderr",
    )

    with patch(
        "src.network.ebpf.loader.program_loader.safe_run",
        side_effect=[which_result, timeout],
    ):
        with patch.object(Path, "mkdir"):
            assert loader.load_via_bpftool(program_path, EBPFProgramType.XDP) == (
                None,
                None,
            )

    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_program_loader_bpftool_load_timeout"
    assert payload["status"] == "failure"
    assert payload["command"] == [
        "bpftool",
        "prog",
        "load",
        "[redacted]",
        "[redacted]",
    ]
    assert payload["error"]["type"] == "TimeoutExpired"
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        b"secret timeout output"
    ).hexdigest()
    assert str(program_path) not in str(payload)
    assert "secret timeout output" not in str(payload)
    assert "secret timeout stderr" not in str(payload)
