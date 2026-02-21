import os
import sys
from types import SimpleNamespace
import types
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

if "aiohttp_cors" not in sys.modules:
    class _CorsRegistry:
        def add(self, _route):
            return None

    class _ResourceOptions:
        def __init__(self, **_kwargs):
            pass

    sys.modules["aiohttp_cors"] = types.SimpleNamespace(
        setup=lambda _app, defaults=None: _CorsRegistry(),
        ResourceOptions=_ResourceOptions,
    )

import src.network.proxy_orchestrator as mod
from src.network.residential_proxy_manager import ProxyStatus


def _proxy(proxy_id: str, status):
    return SimpleNamespace(id=proxy_id, status=status)


def _build_config(*, metrics_enabled: bool = True):
    return SimpleNamespace(
        metrics=SimpleNamespace(enabled=metrics_enabled),
        selection=SimpleNamespace(
            strategy="latency",
            latency_weight=0.4,
            success_weight=0.3,
            stability_weight=0.2,
            geographic_weight=0.1,
        ),
        health_check=SimpleNamespace(interval_seconds=10, unhealthy_threshold=3),
        security=SimpleNamespace(
            api_key_required=True,
            rate_limit_requests_per_minute=120,
            jwt_secret="jwt-secret",
        ),
        control_plane_host="127.0.0.1",
        control_plane_port=8088,
    )


def _patch_initialize_dependencies(monkeypatch, *, metrics_enabled: bool = True):
    calls = {}
    config = _build_config(metrics_enabled=metrics_enabled)
    configured_proxies = [
        _proxy("p-1", ProxyStatus.HEALTHY),
        _proxy("p-2", ProxyStatus.BANNED),
    ]

    class _FakeConfigManager:
        def __init__(self, config_path=None, environment=None):
            self.config_path = config_path
            self.environment = environment
            self.config = config
            self._on_change = None
            self.started = False
            self.stopped = False
            calls["config_manager"] = self

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

        def get_provider_proxies(self):
            return list(configured_proxies)

        def on_change(self, callback):
            self._on_change = callback

    class _FakeMetricsCollector:
        def __init__(self):
            self.started = False
            self.stopped = False
            calls["metrics_collector"] = self

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

        def get_global_metrics(self):
            return {"requests_total": 7}

    class _FakeSelectionAlgorithm:
        def __init__(self, **kwargs):
            self.default_strategy = kwargs["default_strategy"]
            self.latency_weight = kwargs["latency_weight"]
            self.success_weight = kwargs["success_weight"]
            self.stability_weight = kwargs["stability_weight"]
            self.geographic_weight = kwargs["geographic_weight"]
            calls["selection_algorithm"] = self

    class _FakeProxyManager:
        def __init__(self, health_check_interval, max_failures):
            self.health_check_interval = health_check_interval
            self.max_failures = max_failures
            self.proxies = []
            self.started = False
            self.stopped = False
            calls["proxy_manager"] = self

        def add_proxy(self, proxy):
            self.proxies.append(proxy)

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

    class _FakeControlPlane:
        def __init__(self, proxy_manager, host, port):
            self.proxy_manager = proxy_manager
            self.host = host
            self.port = port
            self.started = False
            self.stopped = False
            calls["control_plane"] = self

        async def start(self):
            self.started = True

        async def stop(self):
            self.stopped = True

    class _FakeReputationScoringSystem:
        def export_stats(self):
            return {"tracked_domains": 3}

    monkeypatch.setattr(mod, "ProxyConfigManager", _FakeConfigManager)
    monkeypatch.setattr(mod, "create_default_collector", lambda: _FakeMetricsCollector())
    monkeypatch.setattr(mod, "SelectionStrategy", lambda value: f"strategy:{value}")
    monkeypatch.setattr(mod, "ProxySelectionAlgorithm", _FakeSelectionAlgorithm)
    monkeypatch.setattr(mod, "ResidentialProxyManager", _FakeProxyManager)
    monkeypatch.setattr(mod, "ReputationScoringSystem", _FakeReputationScoringSystem)
    monkeypatch.setattr(mod, "ProxyControlPlane", _FakeControlPlane)

    def _fake_auth_middleware(**kwargs):
        calls["auth_kwargs"] = kwargs
        return {"auth": kwargs}

    monkeypatch.setattr(mod, "create_auth_middleware", _fake_auth_middleware)
    return calls


def test_orchestrator_status_defaults_and_serialization():
    status = mod.OrchestratorStatus(state="initializing")
    assert status.components_ready == {}

    status.started_at = datetime(2026, 1, 1, 0, 0, 0)
    status.active_proxies = 5
    status.healthy_proxies = 4
    status.total_requests = 77
    status.error_count = 2
    payload = status.to_dict()

    assert payload["state"] == "initializing"
    assert payload["started_at"] == "2026-01-01T00:00:00"
    assert payload["proxies"]["active"] == 5
    assert payload["proxies"]["healthy"] == 4
    assert payload["requests"]["total"] == 77
    assert payload["requests"]["errors"] == 2


@pytest.mark.asyncio
async def test_initialize_success_sets_components_ready(monkeypatch):
    calls = _patch_initialize_dependencies(monkeypatch, metrics_enabled=True)
    orchestrator = mod.ProxyOrchestrator(config_path="cfg.yml")

    await orchestrator.initialize()

    assert orchestrator.status.state == "running"
    assert orchestrator.status.started_at is not None
    assert orchestrator.status.components_ready == {
        "config": True,
        "metrics": True,
        "reputation": True,
        "selection": True,
        "proxy_manager": True,
        "auth": True,
        "control_plane": True,
    }
    assert calls["config_manager"].started is True
    assert calls["metrics_collector"].started is True
    assert calls["proxy_manager"].started is True
    assert calls["control_plane"].started is True
    assert calls["config_manager"]._on_change == orchestrator._on_config_change
    assert len(calls["proxy_manager"].proxies) == 2
    assert calls["auth_kwargs"]["jwt_secret"] == "jwt-secret"
    assert calls["auth_kwargs"]["require_auth"] is True


@pytest.mark.asyncio
async def test_initialize_without_metrics_enabled_skips_collector_start(monkeypatch):
    calls = _patch_initialize_dependencies(monkeypatch, metrics_enabled=False)
    orchestrator = mod.ProxyOrchestrator()

    await orchestrator.initialize()

    assert calls["metrics_collector"].started is False
    assert orchestrator.status.components_ready["metrics"] is True


@pytest.mark.asyncio
async def test_initialize_failure_marks_failed(monkeypatch):
    class _FailingConfigManager:
        def __init__(self, config_path=None, environment=None):
            self.config_path = config_path
            self.environment = environment

        async def start(self):
            raise RuntimeError("config boom")

    monkeypatch.setattr(mod, "ProxyConfigManager", _FailingConfigManager)
    orchestrator = mod.ProxyOrchestrator()

    with pytest.raises(RuntimeError, match="config boom"):
        await orchestrator.initialize()
    assert orchestrator.status.state == "failed"


@pytest.mark.asyncio
async def test_on_config_change_updates_weights_and_proxy_pool():
    orchestrator = mod.ProxyOrchestrator()
    orchestrator.selection_algorithm = SimpleNamespace(
        latency_weight=0.0,
        success_weight=0.0,
        stability_weight=0.0,
        geographic_weight=0.0,
    )
    orchestrator.proxy_manager = SimpleNamespace(
            proxies=[
            _proxy("p-1", ProxyStatus.HEALTHY),
            _proxy("p-2", ProxyStatus.DEGRADED),
        ],
        add_proxy=lambda p: orchestrator.proxy_manager.proxies.append(p),
    )
    orchestrator.config_manager = SimpleNamespace(
        get_provider_proxies=lambda: [
            _proxy("p-2", ProxyStatus.DEGRADED),
            _proxy("p-3", ProxyStatus.HEALTHY),
        ]
    )

    new_config = SimpleNamespace(
        selection=SimpleNamespace(
            latency_weight=0.5,
            success_weight=0.2,
            stability_weight=0.2,
            geographic_weight=0.1,
        )
    )

    await orchestrator._on_config_change(new_config)

    assert orchestrator.selection_algorithm.latency_weight == 0.5
    assert orchestrator.selection_algorithm.success_weight == 0.2
    assert orchestrator.selection_algorithm.stability_weight == 0.2
    assert orchestrator.selection_algorithm.geographic_weight == 0.1
    proxy_ids = {p.id for p in orchestrator.proxy_manager.proxies}
    assert proxy_ids == {"p-2", "p-3"}


@pytest.mark.asyncio
async def test_update_status_and_signal_handler():
    orchestrator = mod.ProxyOrchestrator()
    orchestrator.status.started_at = datetime.utcnow() - timedelta(seconds=2)
    orchestrator.proxy_manager = SimpleNamespace(
            proxies=[
            _proxy("h-1", ProxyStatus.HEALTHY),
            _proxy("d-1", ProxyStatus.DEGRADED),
            _proxy("h-2", ProxyStatus.HEALTHY),
        ]
    )

    await orchestrator._update_status()
    assert orchestrator.status.uptime_seconds > 0
    assert orchestrator.status.active_proxies == 3
    assert orchestrator.status.healthy_proxies == 2

    assert orchestrator._shutdown_event.is_set() is False
    orchestrator._signal_handler()
    assert orchestrator._shutdown_event.is_set() is True


@pytest.mark.asyncio
async def test_shutdown_continues_when_component_stop_fails(caplog):
    class _Component:
        def __init__(self, *, fail=False):
            self.fail = fail
            self.stopped = False

        async def stop(self):
            if self.fail:
                raise RuntimeError("stop failed")
            self.stopped = True

    orchestrator = mod.ProxyOrchestrator()
    orchestrator.control_plane = _Component()
    orchestrator.proxy_manager = _Component(fail=True)
    orchestrator.metrics_collector = _Component()
    orchestrator.config_manager = _Component()
    orchestrator.status.components_ready = {
        "control_plane": True,
        "proxy_manager": True,
        "metrics": True,
        "config": True,
    }

    with caplog.at_level("ERROR"):
        await orchestrator.shutdown()

    assert orchestrator.status.state == "stopped"
    assert orchestrator.status.components_ready["control_plane"] is False
    assert orchestrator.status.components_ready["metrics"] is False
    assert orchestrator.status.components_ready["config"] is False
    assert orchestrator.status.components_ready["proxy_manager"] is True
    assert "Error shutting down proxy_manager" in caplog.text


@pytest.mark.asyncio
async def test_metrics_summary_and_health_report():
    orchestrator = mod.ProxyOrchestrator()
    no_collector = await orchestrator.get_metrics_summary()
    assert no_collector["error"] == "Metrics collector not initialized"

    orchestrator.metrics_collector = SimpleNamespace(
        get_global_metrics=lambda: {"requests_total": 11}
    )
    summary = await orchestrator.get_metrics_summary()
    assert summary["requests_total"] == 11

    orchestrator.proxy_manager = SimpleNamespace(
            proxies=[
            _proxy("h-1", ProxyStatus.HEALTHY),
            _proxy("b-1", ProxyStatus.BANNED),
            _proxy("u-1", ProxyStatus.UNHEALTHY),
        ]
    )
    orchestrator.reputation_system = SimpleNamespace(
        export_stats=lambda: {"tracked_domains": 9}
    )

    report = await orchestrator.get_health_report()
    assert report["proxies"]["total"] == 3
    assert report["proxies"]["by_status"]["healthy"] == 1
    assert report["proxies"]["by_status"]["banned"] == 1
    assert report["proxies"]["by_status"]["unhealthy"] == 1
    assert report["reputation"]["tracked_domains"] == 9


def test_get_status_returns_internal_status_object():
    orchestrator = mod.ProxyOrchestrator()
    assert orchestrator.get_status() is orchestrator.status


@pytest.mark.asyncio
async def test_run_registers_signals_and_calls_shutdown(monkeypatch):
    orchestrator = mod.ProxyOrchestrator()
    captured = {"signals": [], "shutdown_calls": 0}

    class _Loop:
        def add_signal_handler(self, sig, handler):
            captured["signals"].append(sig)
            assert callable(handler)

    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _Loop())

    async def _update_status_once():
        orchestrator._shutdown_event.set()

    async def _shutdown():
        captured["shutdown_calls"] += 1

    orchestrator._update_status = _update_status_once
    orchestrator.shutdown = _shutdown

    await orchestrator.run()

    assert set(captured["signals"]) == {mod.signal.SIGTERM, mod.signal.SIGINT}
    assert captured["shutdown_calls"] == 1


@pytest.mark.asyncio
async def test_run_handles_timeout_branch(monkeypatch):
    orchestrator = mod.ProxyOrchestrator()
    calls = {"wait_for": 0, "shutdown": 0}

    class _Loop:
        def add_signal_handler(self, sig, handler):
            assert sig in (mod.signal.SIGTERM, mod.signal.SIGINT)
            assert callable(handler)

    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _Loop())

    async def _update_status():
        return None

    async def _wait_for(event_wait, timeout):
        calls["wait_for"] += 1
        assert timeout == 10.0
        if calls["wait_for"] == 1:
            raise mod.asyncio.TimeoutError()
        orchestrator._shutdown_event.set()
        return await event_wait

    async def _shutdown():
        calls["shutdown"] += 1

    orchestrator._update_status = _update_status
    orchestrator.shutdown = _shutdown
    monkeypatch.setattr(mod.asyncio, "wait_for", _wait_for)

    await orchestrator.run()

    assert calls["wait_for"] == 2
    assert calls["shutdown"] == 1


@pytest.mark.asyncio
async def test_run_handles_status_update_error_branch(monkeypatch, caplog):
    orchestrator = mod.ProxyOrchestrator()
    state = {"calls": 0, "slept": 0, "shutdown": 0}

    class _Loop:
        def add_signal_handler(self, sig, handler):
            assert sig in (mod.signal.SIGTERM, mod.signal.SIGINT)
            assert callable(handler)

    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _Loop())

    async def _update_status():
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("status boom")
        orchestrator._shutdown_event.set()

    async def _wait_for(event_wait, timeout):
        assert timeout == 10.0
        return await event_wait

    async def _sleep(seconds):
        assert seconds == 5
        state["slept"] += 1

    async def _shutdown():
        state["shutdown"] += 1

    orchestrator._update_status = _update_status
    orchestrator.shutdown = _shutdown
    monkeypatch.setattr(mod.asyncio, "wait_for", _wait_for)
    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)

    with caplog.at_level("ERROR"):
        await orchestrator.run()

    assert state["calls"] >= 2
    assert state["slept"] == 1
    assert state["shutdown"] == 1
    assert "Status update error: status boom" in caplog.text


@pytest.mark.asyncio
async def test_main_success_path(monkeypatch):
    calls = {"init": 0, "run": 0, "basic_config": 0}

    class _FakeOrchestrator:
        async def initialize(self):
            calls["init"] += 1

        async def run(self):
            calls["run"] += 1

    def _basic_config(**kwargs):
        calls["basic_config"] += 1
        assert kwargs["level"] == mod.logging.INFO
        assert "format" in kwargs

    monkeypatch.setattr(mod, "ProxyOrchestrator", _FakeOrchestrator)
    monkeypatch.setattr(mod.logging, "basicConfig", _basic_config)

    await mod.main()

    assert calls["basic_config"] == 1
    assert calls["init"] == 1
    assert calls["run"] == 1


@pytest.mark.asyncio
async def test_main_logs_and_reraises_on_failure(monkeypatch, caplog):
    class _FailingOrchestrator:
        async def initialize(self):
            raise RuntimeError("init failed")

        async def run(self):  # pragma: no cover - should not be called
            raise AssertionError("run should not be called")

    monkeypatch.setattr(mod, "ProxyOrchestrator", _FailingOrchestrator)
    monkeypatch.setattr(mod.logging, "basicConfig", lambda **kwargs: None)

    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError, match="init failed"):
            await mod.main()
    assert "Orchestrator failed: init failed" in caplog.text
