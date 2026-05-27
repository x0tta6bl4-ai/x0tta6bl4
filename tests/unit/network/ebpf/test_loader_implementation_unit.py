import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.network.ebpf import loader_implementation as loader_impl
from src.network.ebpf.loader_implementation import EBPFLoaderImplementation


@pytest.fixture
def loader(tmp_path):
    return EBPFLoaderImplementation(programs_dir=tmp_path)


def test_verify_program_detached_fails_closed_on_ip_link_error(loader, monkeypatch):
    loader.loaded_programs["p1"] = {"attached_to": "eth0"}

    def fake_run(cmd, capture_output, text, timeout):
        assert cmd == ["ip", "link", "show", "dev", "eth0"]
        return SimpleNamespace(returncode=1, stdout="", stderr="missing device")

    monkeypatch.setattr(loader_impl.subprocess, "run", fake_run)

    assert loader._verify_program_detached("p1") is False


def test_verify_program_detached_fails_closed_on_exception(loader, monkeypatch):
    loader.loaded_programs["p1"] = {"attached_to": "eth0"}

    def fake_run(cmd, capture_output, text, timeout):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

    monkeypatch.setattr(loader_impl.subprocess, "run", fake_run)

    assert loader._verify_program_detached("p1") is False


def test_verify_program_detached_detects_xdp_attachment(loader, monkeypatch):
    loader.loaded_programs["p1"] = {"attached_to": "eth0"}

    monkeypatch.setattr(
        loader_impl.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500\n    xdp id 42",
            stderr="",
        ),
    )

    assert loader._verify_program_detached("p1") is False


def test_verify_program_detached_accepts_no_xdp_or_xdp_off(loader, monkeypatch):
    loader.loaded_programs["p1"] = {"attached_to": "eth0"}

    monkeypatch.setattr(
        loader_impl.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500",
            stderr="",
        ),
    )
    assert loader._verify_program_detached("p1") is True

    monkeypatch.setattr(
        loader_impl.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout="2: eth0: <BROADCAST,MULTICAST,UP> mtu 1500\n    xdp off",
            stderr="",
        ),
    )
    assert loader._verify_program_detached("p1") is True


def test_release_bpf_maps_removes_pinned_file(loader, tmp_path):
    pinned = tmp_path / "pinned_map"
    pinned.write_text("map")
    loader.loaded_programs["p1"] = {"pinned_path": str(pinned)}

    assert loader._release_bpf_maps("p1") is True
    assert not pinned.exists()


def test_release_bpf_maps_removes_pinned_directory(loader, tmp_path):
    pinned = tmp_path / "pinned_maps"
    pinned.mkdir()
    (pinned / "map0").write_text("map")
    loader.loaded_programs["p1"] = {"pinned_path": str(pinned)}

    assert loader._release_bpf_maps("p1") is True
    assert not pinned.exists()


def test_release_bpf_maps_fails_when_pinned_path_cannot_be_removed(
    loader, monkeypatch
):
    class FailingPath:
        def exists(self):
            return True

        def is_dir(self):
            return False

        def unlink(self):
            raise PermissionError("no perms")

    loader.loaded_programs["p1"] = {"pinned_path": "/sys/fs/bpf/pinned_map"}
    monkeypatch.setattr(loader_impl, "Path", lambda _path: FailingPath())

    assert loader._release_bpf_maps("p1") is False


def test_detach_complete_returns_false_when_verification_fails(loader, monkeypatch):
    monkeypatch.setattr(loader, "detach_from_interface", lambda *_args: True)
    monkeypatch.setattr(loader, "_verify_program_detached", lambda _program_id: False)

    assert loader.detach_from_interface_complete("p1", "eth0") is False


def test_unload_complete_aborts_when_map_release_fails(loader, monkeypatch):
    loader.loaded_programs["p1"] = {"pinned_path": "/sys/fs/bpf/pinned_map"}
    unload_program = Mock(return_value=True)

    monkeypatch.setattr(loader, "_verify_program_detached", lambda _program_id: True)
    monkeypatch.setattr(loader, "_release_bpf_maps", lambda _program_id: False)
    monkeypatch.setattr(loader, "unload_program", unload_program)

    assert loader.unload_program_complete("p1") is False
    unload_program.assert_not_called()
