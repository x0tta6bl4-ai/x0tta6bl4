from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import src.network.ebpf.cli as mod


class _Loader:
    def __init__(self, programs_dir: Path | None = None):
        self._programs = []
        self._iface_programs = {}
        self._stats = {}
        self._load_result = "prog-1"
        self._load_exc = None
        self._unload_result = True
        self._unload_exc = None
        self._attach_result = True
        self._attach_exc = None
        self._detach_result = True
        self._detach_exc = None
        self.programs_dir = programs_dir or Path("/tmp/does-not-exist")

    def list_loaded_programs(self):
        return self._programs

    def get_interface_programs(self, iface: str):
        return self._iface_programs.get(iface, [])

    def get_stats(self):
        return self._stats

    def load_program(self, *_args, **_kwargs):
        if self._load_exc:
            raise self._load_exc
        return self._load_result

    def unload_program(self, *_args, **_kwargs):
        if self._unload_exc:
            raise self._unload_exc
        return self._unload_result

    def attach_to_interface(self, *_args, **_kwargs):
        if self._attach_exc:
            raise self._attach_exc
        return self._attach_result

    def detach_from_interface(self, *_args, **_kwargs):
        if self._detach_exc:
            raise self._detach_exc
        return self._detach_result


def _make_cli(loader: _Loader | None = None, interface: str = "eth9") -> mod.EBPFCLI:
    cli = mod.EBPFCLI(interface=interface)
    if loader is not None:
        cli._loader = loader
    return cli


def test_colorize_respects_tty(monkeypatch):
    monkeypatch.setattr(mod.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    assert mod.colorize("x", mod.Colors.GREEN).startswith(mod.Colors.GREEN)

    monkeypatch.setattr(mod.sys, "stdout", SimpleNamespace(isatty=lambda: False))
    assert mod.colorize("x", mod.Colors.GREEN) == "x"


def test_loader_property_lazy_initialization(monkeypatch):
    sentinel = _Loader()
    monkeypatch.setattr(mod, "EBPFLoader", lambda: sentinel)
    cli = mod.EBPFCLI()
    assert cli._loader is None
    assert cli.loader is sentinel
    assert cli.loader is sentinel


def test_cmd_status_prints_programs_and_drop_rate(capsys):
    loader = _Loader()
    loader._programs = [
        {"id": "p1", "type": "xdp", "attached_to": "eth0"},
        {"id": "p2", "type": "tc"},
    ]
    loader._iface_programs = {"eth9": ["p1"], "lo": []}
    loader._stats = {
        "total_packets": 100,
        "passed_packets": 90,
        "dropped_packets": 10,
        "forwarded_packets": 42,
    }

    cli = _make_cli(loader)
    cli.cmd_status(SimpleNamespace())

    out = capsys.readouterr().out
    assert "Loaded Programs:" in out
    assert "Interface Attachments:" in out
    assert "Drop rate:" in out


def test_cmd_load_success_and_failures():
    loader = _Loader()
    cli = _make_cli(loader)

    ok_args = SimpleNamespace(program="test.o", type="xdp")
    assert cli.cmd_load(ok_args) == 0

    bad_type_args = SimpleNamespace(program="test.o", type="invalid")
    assert cli.cmd_load(bad_type_args) == 1

    loader._load_exc = RuntimeError("boom")
    assert cli.cmd_load(ok_args) == 1


def test_cmd_unload_attach_detach_paths():
    loader = _Loader()
    cli = _make_cli(loader)

    assert cli.cmd_unload(SimpleNamespace(program_id="p1")) == 0
    loader._unload_result = False
    assert cli.cmd_unload(SimpleNamespace(program_id="p1")) == 1
    loader._unload_exc = RuntimeError("unload")
    assert cli.cmd_unload(SimpleNamespace(program_id="p1")) == 1

    assert (
        cli.cmd_attach(SimpleNamespace(program_id="p1", interface="eth0", mode="skb"))
        == 0
    )
    loader._attach_result = False
    assert (
        cli.cmd_attach(SimpleNamespace(program_id="p1", interface="eth0", mode="skb"))
        == 1
    )
    loader._attach_exc = RuntimeError("attach")
    assert (
        cli.cmd_attach(SimpleNamespace(program_id="p1", interface="eth0", mode="skb"))
        == 1
    )

    assert cli.cmd_detach(SimpleNamespace(program_id="p1", interface="eth0")) == 0
    loader._detach_result = False
    assert cli.cmd_detach(SimpleNamespace(program_id="p1", interface="eth0")) == 1
    loader._detach_exc = RuntimeError("detach")
    assert cli.cmd_detach(SimpleNamespace(program_id="p1", interface="eth0")) == 1


def test_cmd_stats_with_json_output(capsys):
    loader = _Loader()
    loader._stats = {"total_packets": 7, "passed_packets": 6}

    cli = _make_cli(loader)
    cli.cmd_stats(SimpleNamespace(json=True))

    out = capsys.readouterr().out
    assert "Metric" in out
    assert '"total_packets": 7' in out


def test_cmd_flows_branches(monkeypatch, capsys):
    cli = _make_cli(_Loader())
    args = SimpleNamespace(source=None, dest=None, protocol=None, limit=5, json=True)

    monkeypatch.setattr(mod, "CILIUM_AVAILABLE", False)
    assert cli.cmd_flows(args) == 1

    class _Cilium:
        def __init__(self, **_kwargs):
            pass

        def get_hubble_like_flows(self, **_kwargs):
            return [
                {
                    "time": "2026-02-16T00:00:00Z",
                    "source": {"ip": "10.0.0.1", "port": 1234},
                    "destination": {"ip": "10.0.0.2", "port": 443},
                    "IP": {"protocol": "TCP"},
                    "Verdict": "forwarded",
                }
            ]

    monkeypatch.setattr(mod, "CILIUM_AVAILABLE", True)
    monkeypatch.setattr(mod, "CiliumLikeIntegration", _Cilium)
    assert cli.cmd_flows(args) == 0
    out = capsys.readouterr().out
    assert "Network Flows" in out
    assert "forwarded" in out

    class _EmptyCilium:
        def __init__(self, **_kwargs):
            pass

        def get_hubble_like_flows(self, **_kwargs):
            return []

    monkeypatch.setattr(mod, "CiliumLikeIntegration", _EmptyCilium)
    assert cli.cmd_flows(args) == 0

    class _BrokenCilium:
        def __init__(self, **_kwargs):
            pass

        def get_hubble_like_flows(self, **_kwargs):
            raise RuntimeError("flow error")

    monkeypatch.setattr(mod, "CiliumLikeIntegration", _BrokenCilium)
    assert cli.cmd_flows(args) == 1


def test_cmd_health_basic_and_orchestrator_paths(monkeypatch):
    loader = _Loader()
    loader._programs = [{"id": "p1"}]
    loader._stats = {"total_packets": 1}
    cli = _make_cli(loader)

    monkeypatch.setattr(mod, "ORCHESTRATOR_AVAILABLE", False)
    assert cli.cmd_health(SimpleNamespace()) == 0

    def _bad_stats():
        raise RuntimeError("stats fail")

    loader.get_stats = _bad_stats
    assert cli.cmd_health(SimpleNamespace()) == 1

    class _Orchestrator:
        def health_check(self):
            return {
                "healthy": True,
                "checks": {
                    "loader": {"status": "healthy", "programs": 1},
                    "metrics": {"status": "healthy"},
                },
            }

    monkeypatch.setattr(mod, "ORCHESTRATOR_AVAILABLE", True)
    monkeypatch.setattr(mod, "create_orchestrator", lambda interface: _Orchestrator())
    assert cli.cmd_health(SimpleNamespace()) == 0

    class _BadOrchestrator:
        def health_check(self):
            return {
                "healthy": False,
                "checks": {"loader": {"status": "error", "reason": "bad"}},
            }

    monkeypatch.setattr(mod, "create_orchestrator", lambda interface: _BadOrchestrator())
    assert cli.cmd_health(SimpleNamespace()) == 1

    def _raise(_interface):
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "create_orchestrator", _raise)
    assert cli.cmd_health(SimpleNamespace()) == 1


def test_cmd_list_programs_variants(tmp_path, capsys):
    loader = _Loader(programs_dir=tmp_path / "missing")
    cli = _make_cli(loader)

    assert cli.cmd_list_programs(SimpleNamespace()) == 1

    programs_dir = tmp_path / "programs"
    programs_dir.mkdir()
    loader.programs_dir = programs_dir
    assert cli.cmd_list_programs(SimpleNamespace()) == 0

    (programs_dir / "a_xdp.o").write_bytes(b"ELF")
    (programs_dir / "b_tc.o").write_bytes(b"ELF")

    assert cli.cmd_list_programs(SimpleNamespace()) == 0
    out = capsys.readouterr().out
    assert "a_xdp.o" in out
    assert "b_tc.o" in out


def test_create_parser_parses_commands():
    parser = mod.create_parser()

    args = parser.parse_args(["status"])
    assert args.command == "status"
    assert args.interface == "eth0"

    args = parser.parse_args(["-i", "lo", "attach", "prog1", "eth1", "-m", "drv"])
    assert args.command == "attach"
    assert args.interface == "eth1"
    assert args.mode == "drv"


def test_main_dispatch_no_command_and_unknown(monkeypatch):
    monkeypatch.setattr(mod.sys, "argv", ["x0tta6bl4-ebpf"])
    assert mod.main() == 0

    class _FakeCli:
        def __init__(self, interface="eth0"):
            self.interface = interface

        def cmd_status(self, args):
            return 7

        cmd_load = cmd_unload = cmd_attach = cmd_detach = cmd_stats = cmd_flows = cmd_health = cmd_list_programs = cmd_status

    monkeypatch.setattr(mod, "EBPFCLI", _FakeCli)
    monkeypatch.setattr(mod.sys, "argv", ["x0tta6bl4-ebpf", "status"])
    assert mod.main() == 7

    class _Parser:
        def parse_args(self):
            return SimpleNamespace(verbose=False, command="weird", interface="eth0")

        def print_help(self):
            return None

    monkeypatch.setattr(mod, "create_parser", lambda: _Parser())
    assert mod.main() == 1
