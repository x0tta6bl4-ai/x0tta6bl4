from __future__ import annotations

import asyncio

import pytest

import src.network.ebpf.ebpf_orchestrator as mod


class _Component:
    def __init__(self, name: str):
        self.name = name
        self.started = 0
        self.stopped = 0
        self.healthy = True
        self.start_exc = None
        self.stop_exc = None
        self.health_exc = None
        self.status_exc = None
        self.stats_exc = None

    async def start(self):
        self.started += 1
        if self.start_exc:
            raise self.start_exc

    async def stop(self):
        self.stopped += 1
        if self.stop_exc:
            raise self.stop_exc

    async def is_healthy(self):
        if self.health_exc:
            raise self.health_exc
        return self.healthy

    def get_status(self):
        if self.status_exc:
            raise self.status_exc
        return {"status": "healthy", "name": self.name}

    def get_stats(self):
        if self.stats_exc:
            raise self.stats_exc
        return {"events": self.started}


class _Loader(_Component):
    def __init__(self):
        super().__init__("loader")
        self.programs = [{"id": "p1"}]
        self.load_exc = None
        self.unload_exc = None
        self.attach_exc = None
        self.detach_exc = None

    def list_loaded_programs(self):
        return self.programs

    async def load_program(self, program_name: str, program_path: str, **_kwargs):
        if self.load_exc:
            raise self.load_exc
        return {"success": True, "program": program_name, "path": program_path}

    async def unload_program(self, program_name: str):
        if self.unload_exc:
            raise self.unload_exc
        return {"success": True, "program": program_name}

    async def attach_program(self, program_name: str, interface: str):
        if self.attach_exc:
            raise self.attach_exc
        return {"success": True, "program": program_name, "interface": interface}

    async def detach_program(self, program_name: str, interface: str):
        if self.detach_exc:
            raise self.detach_exc
        return {"success": True, "program": program_name, "interface": interface}


class _Cilium(_Component):
    def __init__(self):
        super().__init__("cilium")
        self.flow_metrics = {"flows": [{"source": "10.0.0.1", "destination": "10.0.0.2"}]}

    def get_flow_metrics(self):
        return self.flow_metrics


@pytest.fixture
def orchestrator_setup(monkeypatch):
    loader = _Loader()
    probes = _Component("probes")
    metrics = _Component("metrics")
    cilium = _Cilium()
    fallback = _Component("fallback")
    mapek = _Component("mapek")
    ringbuf = _Component("ring_buffer")

    monkeypatch.setattr(mod, "EBPFLoader", lambda: loader)
    monkeypatch.setattr(mod, "MeshNetworkProbes", lambda _iface: probes)
    monkeypatch.setattr(mod, "EBPFMetricsExporter", lambda port, path: metrics)
    monkeypatch.setattr(mod, "CiliumLikeIntegration", lambda _iface: cilium)
    monkeypatch.setattr(mod, "DynamicFallbackController", lambda: fallback)
    monkeypatch.setattr(mod, "EBPFMAPEKIntegration", lambda _metrics: mapek)
    monkeypatch.setattr(mod, "RingBufferReader", lambda buffer_size: ringbuf)

    cfg = mod.OrchestratorConfig(interface="eth0", health_check_interval=0)
    orch = mod.EBPFOrchestrator(cfg)
    return orch, {
        "loader": loader,
        "probes": probes,
        "metrics": metrics,
        "cilium": cilium,
        "fallback": fallback,
        "mapek": mapek,
        "ring_buffer": ringbuf,
    }


@pytest.mark.asyncio
async def test_start_and_stop_lifecycle(orchestrator_setup):
    orch, comps = orchestrator_setup

    await orch.start()
    assert orch.status == mod.OrchestratorStatus.RUNNING
    assert comps["loader"].started == 1
    assert comps["ring_buffer"].started == 1
    assert comps["mapek"].started == 1

    await orch.start()
    assert comps["loader"].started == 1

    await orch.stop()
    assert orch.status == mod.OrchestratorStatus.STOPPED
    assert comps["loader"].stopped == 1
    assert comps["ring_buffer"].stopped == 1

    await orch.stop()
    assert orch.status == mod.OrchestratorStatus.STOPPED


@pytest.mark.asyncio
async def test_start_failure_sets_error_and_calls_stop_components(monkeypatch, orchestrator_setup):
    orch, comps = orchestrator_setup
    comps["probes"].start_exc = RuntimeError("start failed")

    state = {"stopped": False}

    async def _stop_components():
        state["stopped"] = True

    monkeypatch.setattr(orch, "_stop_components", _stop_components, raising=False)

    with pytest.raises(RuntimeError, match="start failed"):
        await orch.start()

    assert orch.status == mod.OrchestratorStatus.ERROR
    assert state["stopped"] is True


@pytest.mark.asyncio
async def test_start_stop_component_fallback_paths(orchestrator_setup):
    orch, _ = orchestrator_setup

    calls = {"init": 0, "shutdown": 0}

    class _InitOnly:
        async def initialize(self):
            calls["init"] += 1

    class _ShutdownOnly:
        async def shutdown(self):
            calls["shutdown"] += 1

    await orch._start_component(_InitOnly())
    await orch._stop_component(_ShutdownOnly())

    assert calls["init"] == 1
    assert calls["shutdown"] == 1


@pytest.mark.asyncio
async def test_health_checks_and_unhealthy_restarts(monkeypatch, orchestrator_setup):
    orch, comps = orchestrator_setup

    comps["probes"].healthy = False
    comps["fallback"].health_exc = RuntimeError("health err")

    restarted = []

    async def _handle(name, _component):
        restarted.append(name)

    monkeypatch.setattr(orch, "_handle_unhealthy_component", _handle)
    await orch._check_components_health()

    assert "probes" in restarted
    assert "fallback" in restarted


@pytest.mark.asyncio
async def test_handle_unhealthy_component_failure_sets_error(orchestrator_setup):
    orch, _ = orchestrator_setup

    broken = _Component("broken")
    broken.start_exc = RuntimeError("cannot restart")

    await orch._handle_unhealthy_component("broken", broken)
    assert orch.status == mod.OrchestratorStatus.ERROR


@pytest.mark.asyncio
async def test_health_check_loop_cancel_and_error_paths(monkeypatch, orchestrator_setup):
    orch, _ = orchestrator_setup

    orch.status = mod.OrchestratorStatus.RUNNING

    async def _cancel_sleep(_seconds):
        raise asyncio.CancelledError()

    monkeypatch.setattr(mod.asyncio, "sleep", _cancel_sleep)
    await orch._health_check_loop()

    orch.status = mod.OrchestratorStatus.RUNNING

    async def _ok_sleep(_seconds):
        return None

    async def _boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(mod.asyncio, "sleep", _ok_sleep)
    monkeypatch.setattr(orch, "_check_components_health", _boom)
    await orch._health_check_loop()


@pytest.mark.asyncio
async def test_status_stats_and_loader_flow_wrappers(orchestrator_setup):
    orch, comps = orchestrator_setup

    comps["metrics"].status_exc = RuntimeError("status fail")
    comps["mapek"].stats_exc = RuntimeError("stats fail")

    status = orch.get_status()
    assert status["orchestrator_status"] == mod.OrchestratorStatus.STOPPED.value
    assert status["components"]["metrics"]["status"] == "error"

    stats = orch.get_stats()
    assert "error" in stats["mapek"]

    assert orch.list_loaded_programs() == [{"id": "p1"}]
    assert "flows" in orch.get_flows()

    ok_load = await orch.load_program("prog", "prog.o")
    assert ok_load["success"] is True

    ok_attach = await orch.attach_program("prog", interface="eth1")
    assert ok_attach["success"] is True

    ok_detach = await orch.detach_program("prog", interface="eth1")
    assert ok_detach["success"] is True

    ok_unload = await orch.unload_program("prog")
    assert ok_unload["success"] is True

    comps["loader"].load_exc = RuntimeError("load")
    comps["loader"].attach_exc = RuntimeError("attach")
    comps["loader"].detach_exc = RuntimeError("detach")
    comps["loader"].unload_exc = RuntimeError("unload")

    assert (await orch.load_program("prog", "prog.o"))["success"] is False
    assert (await orch.attach_program("prog"))["success"] is False
    assert (await orch.detach_program("prog"))["success"] is False
    assert (await orch.unload_program("prog"))["success"] is False


@pytest.mark.asyncio
async def test_async_context_manager_and_main(monkeypatch, orchestrator_setup):
    orch, _ = orchestrator_setup

    calls = {"start": 0, "stop": 0}

    async def _start():
        calls["start"] += 1

    async def _stop():
        calls["stop"] += 1

    monkeypatch.setattr(orch, "start", _start)
    monkeypatch.setattr(orch, "stop", _stop)

    async with orch:
        pass

    assert calls["start"] == 1
    assert calls["stop"] == 1

    class _MainOrchestrator:
        def __init__(self, _config):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def get_status(self):
            return {"orchestrator_status": "running", "components": {}}

        def list_loaded_programs(self):
            return []

        def get_stats(self):
            return {}

    async def _fast_sleep(_seconds):
        return None

    monkeypatch.setattr(mod, "EBPFOrchestrator", _MainOrchestrator)
    monkeypatch.setattr(mod.asyncio, "sleep", _fast_sleep)

    await mod.main()
