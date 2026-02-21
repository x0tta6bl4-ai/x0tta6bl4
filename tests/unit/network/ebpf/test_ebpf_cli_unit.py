from __future__ import annotations

import csv
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.network.ebpf.ebpf_cli as mod


class _AsyncCtx:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    async def __aenter__(self):
        return self.orchestrator

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Orchestrator:
    def __init__(self):
        self.routes_updated = None
        self.update_result = True
        self.raise_load = False
        self.raise_attach = False
        self.raise_detach = False
        self.raise_unload = False

    def get_status(self):
        return {
            "orchestrator_status": "running",
            "components": {
                "loader": {"status": "healthy"},
                "metrics": {"status": "error", "error": "boom"},
            },
        }

    def list_loaded_programs(self):
        return [
            {
                "id": "p1",
                "path": "/tmp/p1.o",
                "type": "xdp",
                "attached_to": "eth0",
            }
        ]

    async def load_program(self, *_args, **_kwargs):
        if self.raise_load:
            raise RuntimeError("load failed")
        return {"success": True}

    async def attach_program(self, *_args, **_kwargs):
        if self.raise_attach:
            raise RuntimeError("attach failed")
        return {"success": True}

    async def detach_program(self, *_args, **_kwargs):
        if self.raise_detach:
            raise RuntimeError("detach failed")
        return {"success": True}

    async def unload_program(self, *_args, **_kwargs):
        if self.raise_unload:
            raise RuntimeError("unload failed")
        return {"success": True}

    def get_stats(self):
        return {
            "loader": {"loaded": 1, "nested": {"x": 1}},
            "error_comp": {"error": "skip"},
        }

    def get_flows(self):
        return {
            "flows": [
                {
                    "source": "10.0.0.1",
                    "destination": "10.0.0.2",
                    "protocol": "TCP",
                    "packets": 7,
                    "bytes": 512,
                }
            ]
        }

    def update_routes(self, routes):
        self.routes_updated = routes
        return self.update_result


@pytest.mark.asyncio
async def test_run_dispatches_commands(monkeypatch):
    cli = mod.EBPFCLI()
    orchestrator = _Orchestrator()

    monkeypatch.setattr(mod, "EBPFOrchestrator", lambda config: _AsyncCtx(orchestrator))

    called = []

    async def _mark(*_args, **_kwargs):
        called.append(True)

    monkeypatch.setattr(cli, "_handle_status", _mark)
    args = SimpleNamespace(verbose=False, interface="eth0", port=9090, command="status")
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_list", _mark)
    args.command = "list"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_load", _mark)
    args.command = "load"
    args.program_path = "prog.o"
    args.type = "xdp"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_attach", _mark)
    args.command = "attach"
    args.program_name = "prog"
    args.mode = "skb"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_detach", _mark)
    args.command = "detach"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_unload", _mark)
    args.command = "unload"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_stats", _mark)
    args.command = "stats"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_flows", _mark)
    args.command = "flows"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_routes", _mark)
    args.command = "routes"
    assert await cli.run(args) is True
    assert called == [True]

    called.clear()
    monkeypatch.setattr(cli, "_handle_update_routes", _mark)
    args.command = "update-routes"
    args.routes_file = "routes.csv"
    assert await cli.run(args) is True
    assert called == [True]

    args.command = None
    assert await cli.run(args) is False


@pytest.mark.asyncio
async def test_run_handles_context_error(monkeypatch):
    cli = mod.EBPFCLI()

    class _BrokenCtx:
        def __init__(self, _config):
            pass

        async def __aenter__(self):
            raise RuntimeError("ctx failed")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(mod, "EBPFOrchestrator", _BrokenCtx)
    args = SimpleNamespace(verbose=True, interface="eth0", port=9090, command="status")
    assert await cli.run(args) is False


@pytest.mark.asyncio
async def test_handle_status_list_stats_and_flows_output(capsys):
    cli = mod.EBPFCLI()
    orchestrator = _Orchestrator()

    await cli._handle_status(orchestrator)
    await cli._handle_list(orchestrator)
    await cli._handle_stats(orchestrator)
    await cli._handle_flows(orchestrator)

    out = capsys.readouterr().out
    assert "eBPF Orchestrator Status" in out
    assert "Loaded eBPF Programs" in out
    assert "eBPF Statistics" in out
    assert "Network Flow Metrics" in out

    orchestrator.get_flows = lambda: {}
    await cli._handle_flows(orchestrator)
    assert "No flow metrics available" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_handle_load_paths(tmp_path):
    cli = mod.EBPFCLI()
    orchestrator = _Orchestrator()

    missing = tmp_path / "missing.o"
    await cli._handle_load(orchestrator, str(missing), "xdp")

    f = tmp_path / "prog.o"
    f.write_text("dummy")

    await cli._handle_load(orchestrator, str(f), "xdp")

    orchestrator.raise_load = True
    await cli._handle_load(orchestrator, str(f), "xdp")

    with pytest.raises(ValueError):
        await cli._handle_load(orchestrator, str(f), "invalid")


@pytest.mark.asyncio
async def test_handle_attach_detach_unload_paths():
    cli = mod.EBPFCLI()
    orchestrator = _Orchestrator()

    await cli._handle_attach(orchestrator, "prog", "eth0", "skb")
    await cli._handle_detach(orchestrator, "prog", "eth0")
    await cli._handle_unload(orchestrator, "prog")

    orchestrator.raise_attach = True
    orchestrator.raise_detach = True
    orchestrator.raise_unload = True

    await cli._handle_attach(orchestrator, "prog", "eth0", "skb")
    await cli._handle_detach(orchestrator, "prog", "eth0")
    await cli._handle_unload(orchestrator, "prog")


@pytest.mark.asyncio
async def test_handle_routes_branches(monkeypatch, capsys):
    cli = mod.EBPFCLI()
    orchestrator = _Orchestrator()

    class _Result:
        returncode = 0
        stdout = '[{"key":"10.0.0.0/24","value":"10.0.0.1"}]'

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: _Result())
    await cli._handle_routes(orchestrator)
    out = capsys.readouterr().out
    assert "Mesh Routing Table" in out
    assert "10.0.0.0/24 -> 10.0.0.1" in out

    def _no_tool(*_args, **_kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", _no_tool)
    await cli._handle_routes(orchestrator)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "run", _boom)
    await cli._handle_routes(orchestrator)


@pytest.mark.asyncio
async def test_handle_update_routes_branches(tmp_path):
    cli = mod.EBPFCLI()
    orchestrator = _Orchestrator()

    await cli._handle_update_routes(orchestrator, str(tmp_path / "none.csv"))

    empty_file = tmp_path / "empty.csv"
    with open(empty_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["destination", "next_hop"])
        writer.writeheader()
        writer.writerow({"destination": "", "next_hop": ""})
    await cli._handle_update_routes(orchestrator, str(empty_file))

    routes_file = tmp_path / "routes.csv"
    with open(routes_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["destination", "next_hop"])
        writer.writeheader()
        writer.writerow({"destination": "10.0.0.0/24", "next_hop": "10.0.0.1"})
        writer.writerow({"destination": "10.1.0.0/24", "next_hop": "10.1.0.1"})

    orchestrator.update_result = True
    await cli._handle_update_routes(orchestrator, str(routes_file))
    assert orchestrator.routes_updated == {
        "10.0.0.0/24": "10.0.0.1",
        "10.1.0.0/24": "10.1.0.1",
    }

    orchestrator.update_result = False
    await cli._handle_update_routes(orchestrator, str(routes_file))

    def _raise(_routes):
        raise RuntimeError("update fail")

    orchestrator.update_routes = _raise
    await cli._handle_update_routes(orchestrator, str(routes_file))


def test_main_paths(monkeypatch):
    class _Parser:
        def __init__(self, args):
            self._args = args

        def parse_args(self):
            return self._args

        def print_help(self):
            return None

    class _Cli:
        def __init__(self, args, run_result=True):
            self.parser = _Parser(args)
            self._run_result = run_result

        async def run(self, _args):
            return self._run_result

    args_none = SimpleNamespace(command=None)
    monkeypatch.setattr(mod, "EBPFCLI", lambda: _Cli(args_none))
    assert mod.main() == 1

    args_ok = SimpleNamespace(command="status")
    monkeypatch.setattr(mod, "EBPFCLI", lambda: _Cli(args_ok, run_result=True))
    assert mod.main() == 0

    monkeypatch.setattr(mod, "EBPFCLI", lambda: _Cli(args_ok, run_result=False))
    assert mod.main() == 1

    monkeypatch.setattr(mod, "EBPFCLI", lambda: _Cli(args_ok, run_result=True))
    monkeypatch.setattr(mod.asyncio, "run", lambda _cor: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert mod.main() == 1

    monkeypatch.setattr(mod.asyncio, "run", lambda _cor: (_ for _ in ()).throw(RuntimeError("boom")))
    assert mod.main() == 2
