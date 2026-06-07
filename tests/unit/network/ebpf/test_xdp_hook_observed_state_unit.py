import hashlib
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.hooks.xdp_hook import XDPHook


def _hook(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    return XDPHook(event_bus=bus), bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-xdp-hook",
        limit=50,
    )


def _stage_payload(bus, stage):
    for event in reversed(_events(bus)):
        if event.data["stage"] == stage:
            return event.data
    raise AssertionError(f"missing stage {stage}")


def _assert_thinking_context(payload):
    thinking = payload["thinking"]
    techniques = set(thinking["techniques"])
    assert thinking["role"] == "security"
    assert "stride_threat_modeling" in techniques
    assert "zero_trust_review" in techniques
    assert "mape_k" in techniques
    assert "causal_analysis" in techniques
    assert "reverse_planning" in techniques
    assert thinking["applied"]["framing"]["problem"] == "ebpf_xdp_hook_operation"
    constraints = thinking["applied"]["framing"]["constraints"]
    assert constraints["operation"] == payload["operation"]
    assert constraints["stage"] == payload["stage"]
    assert constraints["output_redacted"] is True
    assert "extra_keys" in constraints


def test_xdp_attach_success_publishes_redacted_evidence(tmp_path):
    hook, bus = _hook(tmp_path)
    interface = "eth0"
    program_file = tmp_path / "secret_xdp_prog.o"
    program_file.write_bytes(b"\x7fELF\x02\x01\x01\x00")
    attach_stdout = "secret attach stdout"
    verify_stdout = "secret verify xdp present"

    def mock_path_exists(self):
        path_text = str(self)
        return interface in path_text or "secret_xdp_prog" in path_text

    def mock_subprocess_run(cmd, **_kwargs):
        if cmd == ["ip", "link", "help"]:
            return SimpleNamespace(
                returncode=0,
                stdout="",
                stderr="Usage: ip link set dev DEVICE { xdp | xdpdrv }",
            )
        if cmd[:4] == ["ip", "link", "show", "dev"]:
            return SimpleNamespace(returncode=0, stdout=verify_stdout, stderr="")
        return SimpleNamespace(returncode=0, stdout=attach_stdout, stderr="")

    with (
        patch.object(Path, "exists", mock_path_exists),
        patch.object(Path, "read_text", return_value="up"),
        patch(
            "src.network.ebpf.hooks.xdp_hook.subprocess.run",
            side_effect=mock_subprocess_run,
        ),
    ):
        assert hook.attach(interface, str(program_file), mode="native") is True

    command_payload = _stage_payload(bus, "xdp_attach_command_succeeded")
    assert command_payload["command"] == [
        "ip",
        "link",
        "set",
        "dev",
        "[redacted]",
        "xdpdrv",
        "obj",
        "[redacted]",
        "sec",
        "xdp",
    ]
    assert command_payload["output"]["stdout_sha256"] == hashlib.sha256(
        attach_stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(command_payload)

    verify_payload = _stage_payload(bus, "xdp_attach_verify_succeeded")
    assert verify_payload["command"] == ["ip", "link", "show", "dev", "[redacted]"]
    assert verify_payload["returncode"] == 0
    assert verify_payload["parsed_summary"]["attached"] is True
    assert verify_payload["parsed_summary"]["actual_mode"] == "native"
    assert verify_payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert verify_payload["program_path_hash"] == hashlib.sha256(
        str(program_file).encode("utf-8")
    ).hexdigest()
    assert verify_payload["output"]["stdout_sha256"] == hashlib.sha256(
        verify_stdout.encode("utf-8")
    ).hexdigest()
    assert verify_payload["identity"]["redacted"] is True
    _assert_thinking_context(verify_payload)
    assert interface not in str(verify_payload)
    assert str(program_file) not in str(verify_payload)
    assert verify_stdout not in str(verify_payload)


def test_xdp_detach_verify_failure_publishes_redacted_evidence(tmp_path):
    hook, bus = _hook(tmp_path)
    interface = "eth0"
    hook.attached_programs[interface] = {
        "program": "/secret/path/xdp_prog.o",
        "mode": "generic",
        "actual_mode": "generic",
    }
    detach_stdout = "secret detach stdout"
    verify_stdout = "secret xdp still present"

    def mock_subprocess_run(cmd, **_kwargs):
        if cmd[:4] == ["ip", "link", "show", "dev"]:
            return SimpleNamespace(returncode=0, stdout=verify_stdout, stderr="")
        return SimpleNamespace(returncode=0, stdout=detach_stdout, stderr="")

    with (
        patch.object(Path, "exists", return_value=True),
        patch(
            "src.network.ebpf.hooks.xdp_hook.subprocess.run",
            side_effect=mock_subprocess_run,
        ),
    ):
        assert hook.detach(interface) is False

    payload = _stage_payload(bus, "xdp_detach_verify_failed")
    assert payload["command"] == ["ip", "link", "show", "dev", "[redacted]"]
    assert payload["status"] == "failure"
    assert payload["parsed_summary"] == {"detached": False}
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        verify_stdout.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert verify_stdout not in str(payload)


def test_xdp_attach_program_missing_publishes_redacted_precondition(tmp_path):
    hook, bus = _hook(tmp_path)
    interface = "eth0"
    program_path = str(tmp_path / "secret_missing_prog.o")

    def mock_path_exists(self):
        return interface in str(self)

    with patch.object(Path, "exists", mock_path_exists):
        assert hook.attach(interface, program_path, mode="generic") is False

    payload = _stage_payload(bus, "xdp_attach_program_missing")
    assert payload["status"] == "failure"
    assert payload["parsed_summary"] == {
        "attached": False,
        "reason": "program_missing",
    }
    assert payload["program_path_hash"] == hashlib.sha256(
        program_path.encode("utf-8")
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert program_path not in str(payload)


def test_xdp_driver_support_timeout_publishes_redacted_error(tmp_path):
    hook, bus = _hook(tmp_path)
    interface = "eth0"
    timeout = subprocess.TimeoutExpired(
        cmd="ip link help",
        timeout=2,
        output="secret help stdout",
        stderr="secret help stderr",
    )

    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(Path, "read_text", return_value="up"),
        patch("src.network.ebpf.hooks.xdp_hook.subprocess.run", side_effect=timeout),
    ):
        assert hook._check_driver_support(interface, "native") is False

    payload = _stage_payload(bus, "xdp_driver_support_check_timeout")
    assert payload["command"] == ["ip", "link", "help"]
    assert payload["error"]["type"] == "TimeoutExpired"
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        b"secret help stdout"
    ).hexdigest()
    assert payload["output"]["stderr_sha256"] == hashlib.sha256(
        b"secret help stderr"
    ).hexdigest()
    _assert_thinking_context(payload)
    assert interface not in str(payload)
    assert "secret help stdout" not in str(payload)
    assert "secret help stderr" not in str(payload)
