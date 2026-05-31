import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.network.ebpf.loader.attach_manager import EBPFAttachManager, EBPFAttachMode


def _manager(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    manager = EBPFAttachManager(event_bus=bus)
    return manager, bus


def _events(bus):
    return bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-loader-attach-manager",
        limit=30,
    )


def test_xdp_attach_success_publishes_redacted_ip_link_evidence(
    tmp_path,
    monkeypatch,
):
    manager, bus = _manager(tmp_path)
    interface = "secret0"
    program_path = "/tmp/secret_prog.o"
    stdout = "secret attach output"

    monkeypatch.setattr(manager, "verify_interface", lambda _interface: True)
    monkeypatch.setattr(manager, "_verify_xdp_attachment", lambda _interface: True)
    monkeypatch.setattr(
        "src.network.ebpf.loader.attach_manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert manager.attach_xdp(program_path, interface, EBPFAttachMode.SKB, "prog-1")
    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_attach_manager_xdp_attach_succeeded"
    assert payload["operation"] == "xdp_attach"
    assert payload["read_only"] is False
    assert payload["command"] == [
        "ip",
        "link",
        "set",
        "dev",
        "[redacted]",
        "xdp",
        "obj",
        "[redacted]",
        "sec",
        ".text",
    ]
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["program_path_hash"] == hashlib.sha256(
        program_path.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert payload["identity"]["redacted"] is True
    assert interface not in str(payload)
    assert program_path not in str(payload)
    assert stdout not in str(payload)


def test_xdp_verify_success_publishes_redacted_observation(tmp_path, monkeypatch):
    manager, bus = _manager(tmp_path)
    interface = "secret1"
    stdout = "7: secret1: <BROADCAST> xdp id 42 tag secret"

    monkeypatch.setattr(
        "src.network.ebpf.loader.attach_manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert manager._verify_xdp_attachment(interface) is True
    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_attach_manager_xdp_verify_succeeded"
    assert payload["operation"] == "verify_xdp_attachment"
    assert payload["read_only"] is True
    assert payload["command"] == ["ip", "link", "show", "dev", "[redacted]"]
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert interface not in str(payload)
    assert stdout not in str(payload)


def test_tc_attach_success_publishes_redacted_tc_evidence(tmp_path, monkeypatch):
    manager, bus = _manager(tmp_path)
    interface = "secret2"
    program_path = "/tmp/secret_tc.o"
    stdout = "secret tc attach output"

    monkeypatch.setattr(manager, "verify_interface", lambda _interface: True)
    monkeypatch.setattr(
        "src.network.ebpf.loader.attach_manager.safe_run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        "src.network.ebpf.loader.attach_manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert manager.attach_tc(program_path, interface, "prog-tc")
    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_attach_manager_tc_attach_succeeded"
    assert payload["operation"] == "tc_attach"
    assert payload["command"] == [
        "tc",
        "filter",
        "add",
        "dev",
        "[redacted]",
        "ingress",
        "bpf",
        "da",
        "obj",
        "[redacted]",
        "sec",
        ".text",
    ]
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["program_path_hash"] == hashlib.sha256(
        program_path.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert interface not in str(payload)
    assert program_path not in str(payload)
    assert stdout not in str(payload)


def test_xdp_detach_success_publishes_redacted_ip_link_evidence(
    tmp_path,
    monkeypatch,
):
    manager, bus = _manager(tmp_path)
    interface = "secret3"
    stdout = "secret detach output"

    monkeypatch.setattr(
        "src.network.ebpf.loader.attach_manager.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert manager.detach_xdp(interface) is True
    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_attach_manager_xdp_detach_succeeded"
    assert payload["operation"] == "xdp_detach"
    assert payload["command"] == [
        "ip",
        "link",
        "set",
        "dev",
        "[redacted]",
        "xdp",
        "off",
    ]
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert interface not in str(payload)
    assert stdout not in str(payload)


def test_verify_interface_bring_up_publishes_redacted_evidence(
    tmp_path,
    monkeypatch,
):
    manager, bus = _manager(tmp_path)
    interface = "secret4"
    stdout = "secret bring up output"
    interface_path = MagicMock()
    interface_path.exists.return_value = True
    operstate = MagicMock()
    operstate.exists.return_value = True
    operstate.read_text.return_value = "down\n"
    interface_path.__truediv__ = MagicMock(return_value=operstate)

    monkeypatch.setattr(
        "src.network.ebpf.loader.attach_manager.Path",
        lambda _path: interface_path,
    )
    monkeypatch.setattr(
        "src.network.ebpf.loader.attach_manager.safe_run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=stdout,
            stderr="",
        ),
    )

    assert manager.verify_interface(interface) is True
    payload = _events(bus)[-1].data
    assert payload["stage"] == "loader_attach_manager_interface_bring_up_succeeded"
    assert payload["operation"] == "interface_bring_up"
    assert payload["command"] == ["ip", "link", "set", "dev", "[redacted]", "up"]
    assert payload["interface_hash"] == hashlib.sha256(
        interface.encode("utf-8")
    ).hexdigest()
    assert payload["output"]["stdout_sha256"] == hashlib.sha256(
        stdout.encode("utf-8")
    ).hexdigest()
    assert interface not in str(payload)
    assert stdout not in str(payload)
