import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

try:
    from fastapi import FastAPI

    FASTAPI_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    FASTAPI_AVAILABLE = False

try:
    import src.core.production_lifespan as mod

    MODULE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - import guard
    MODULE_AVAILABLE = False
    IMPORT_ERROR = str(exc)


pytestmark = pytest.mark.skipif(
    not MODULE_AVAILABLE,
    reason=f"production_lifespan module not available: {IMPORT_ERROR if not MODULE_AVAILABLE else ''}",
)


class _DummyTask:
    def __init__(self):
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True

    def __await__(self):
        async def _done():
            return None

        return _done().__await__()


class _CancelledTask:
    def __init__(self):
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True

    def __await__(self):
        async def _raise_cancelled():
            raise asyncio.CancelledError()

        return _raise_cancelled().__await__()


@pytest.mark.asyncio
async def test_startup_initializes_all_components(monkeypatch):
    engine = mod.OptimizationEngine()
    parl = SimpleNamespace(initialize=AsyncMock(), terminate=AsyncMock())
    fl_integration = SimpleNamespace(startup=AsyncMock(), shutdown=AsyncMock())
    mape_k_loop = SimpleNamespace(start=AsyncMock(), stop=AsyncMock())

    monkeypatch.setattr(mod, "MeshNetworkManager", lambda: object())
    monkeypatch.setattr(mod, "PrometheusExporter", lambda: object())
    monkeypatch.setattr(mod, "ZeroTrustValidator", lambda: object())
    monkeypatch.setattr(mod, "ConsciousnessEngine", lambda **_kwargs: object())
    monkeypatch.setattr(mod, "PARLController", lambda **_kwargs: parl)
    monkeypatch.setattr(mod, "create_fl_integration", lambda **_kwargs: fl_integration)
    monkeypatch.setattr(mod, "MAPEKLoop", lambda **_kwargs: mape_k_loop)

    created_tasks = []

    def _fake_create_task(coro):
        coro.close()
        task = _DummyTask()
        created_tasks.append(task)
        return task

    monkeypatch.setattr(mod.asyncio, "create_task", _fake_create_task)

    await engine.startup()

    assert engine.network_manager is not None
    assert engine.parl_controller is parl
    assert engine.fl_integration is fl_integration
    assert engine.mape_k_loop is mape_k_loop
    assert engine.loop_task is created_tasks[0]
    parl.initialize.assert_awaited_once()
    fl_integration.startup.assert_awaited_once()
    mape_k_loop.start.assert_called_once_with(fl_integration=True)


@pytest.mark.asyncio
async def test_startup_swallows_component_exceptions(monkeypatch):
    engine = mod.OptimizationEngine()

    def _raise():
        raise RuntimeError("mesh init failed")

    monkeypatch.setattr(mod, "MeshNetworkManager", _raise)

    # Should not raise, by design ("Zombie mode is better than Dead mode")
    await engine.startup()

    assert engine.network_manager is None
    assert engine.loop_task is None


@pytest.mark.asyncio
async def test_shutdown_stops_components_and_cancels_loop_task():
    engine = mod.OptimizationEngine()
    mape_k_loop = SimpleNamespace(stop=AsyncMock())
    parl = SimpleNamespace(terminate=AsyncMock())
    fl_integration = SimpleNamespace(shutdown=AsyncMock())
    task = _CancelledTask()

    engine.mape_k_loop = mape_k_loop
    engine.parl_controller = parl
    engine.fl_integration = fl_integration
    engine.loop_task = task

    await engine.shutdown()

    mape_k_loop.stop.assert_awaited_once()
    parl.terminate.assert_awaited_once()
    fl_integration.shutdown.assert_awaited_once()
    assert task.cancel_called is True


@pytest.mark.asyncio
@pytest.mark.skipif(not FASTAPI_AVAILABLE, reason="fastapi not available")
async def test_production_lifespan_runs_startup_and_shutdown(monkeypatch):
    fake_engine = SimpleNamespace(startup=AsyncMock(), shutdown=AsyncMock())
    monkeypatch.setattr(mod, "optimization_engine", fake_engine)

    app = FastAPI()
    async with mod.production_lifespan(app):
        fake_engine.startup.assert_awaited_once()
        fake_engine.shutdown.assert_not_awaited()

    fake_engine.shutdown.assert_awaited_once()
