import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import asyncio
from datetime import datetime, timedelta

import pytest

import src.security.vault_monitoring as vm


class _Metric:
    def __init__(self):
        self.incs = []
        self.sets = []

    def inc(self, value=1):
        self.incs.append(value)

    def set(self, value):
        self.sets.append(value)


class _Client:
    def __init__(self):
        self.vault_addr = "http://vault"
        self.authenticated = True
        self.is_healthy = True
        self.is_degraded = False
        self.token_expiry = None
        self.client = object()
        self._health = True

    async def health_check(self):
        return self._health

    def get_cache_stats(self):
        return {"hits": 1, "misses": 0}


def test_get_or_create_metric_returns_existing_collector(monkeypatch):
    existing = type("Collector", (), {"_name": "vault_metric"})()
    fake_registry = type("FakeRegistry", (), {"_names_to_collectors": {"x": existing}})()
    monkeypatch.setattr(vm, "REGISTRY", fake_registry)

    def _metric_class(*_args, **_kwargs):
        raise AssertionError("Should not create new metric when existing collector found")

    result = vm._get_or_create_metric(_metric_class, "vault_metric", "desc")
    assert result is existing
    with pytest.raises(AssertionError):
        _metric_class()


def test_get_or_create_metric_falls_back_to_registry_none(monkeypatch):
    broken_registry = type("BrokenRegistry", (), {"_names_to_collectors": None})()
    monkeypatch.setattr(vm, "REGISTRY", broken_registry)
    calls = []

    def _metric_class(name, description, **kwargs):
        calls.append((name, description, kwargs))
        return {"name": name, "description": description, "kwargs": kwargs}

    result = vm._get_or_create_metric(
        _metric_class, "fallback_metric", "desc", labelnames=["kind"]
    )
    assert result["name"] == "fallback_metric"
    assert calls[0][2]["registry"] is None
    assert calls[0][2]["labelnames"] == ["kind"]


@pytest.fixture
def metric_mocks(monkeypatch):
    expiry = _Metric()
    uptime = _Metric()
    failures = _Metric()
    refresh = _Metric()
    degraded = _Metric()
    monkeypatch.setattr(vm, "vault_token_expiry_seconds", expiry)
    monkeypatch.setattr(vm, "vault_uptime_seconds", uptime)
    monkeypatch.setattr(vm, "vault_health_check_failures", failures)
    monkeypatch.setattr(vm, "vault_token_refresh_count", refresh)
    monkeypatch.setattr(vm, "vault_degraded_mode", degraded)
    return expiry, uptime, failures, refresh, degraded


@pytest.mark.asyncio
async def test_perform_health_check_healthy_updates_metrics(metric_mocks):
    expiry, uptime, failures, refresh, degraded = metric_mocks
    c = _Client()
    monitor = vm.VaultHealthMonitor(c, check_interval=10)
    await monitor._perform_health_check()
    assert uptime.incs == [10]
    assert degraded.sets[-1] == 0
    assert failures.incs == []
    assert monitor._last_health is True


@pytest.mark.asyncio
async def test_perform_health_check_health_change_and_callback(metric_mocks):
    _, uptime, failures, _, degraded = metric_mocks
    c = _Client()
    state = {"seen": []}
    monitor = vm.VaultHealthMonitor(
        c, on_health_change=lambda h: state["seen"].append(h)
    )
    monitor._last_health = True
    c._health = False
    await monitor._perform_health_check()
    assert degraded.sets[-1] == 1
    assert state["seen"] == [False]


@pytest.mark.asyncio
async def test_perform_health_check_exception_path(metric_mocks, monkeypatch):
    _, _, failures, _, degraded = metric_mocks
    c = _Client()

    async def _raise():
        raise RuntimeError("down")

    c.health_check = _raise
    monitor = vm.VaultHealthMonitor(c)
    await monitor._perform_health_check()
    assert failures.incs[-1] == 1
    assert degraded.sets[-1] == 1


@pytest.mark.asyncio
async def test_check_token_expiry_warning_and_reset(metric_mocks):
    expiry, *_ = metric_mocks
    c = _Client()
    called = {"n": 0}
    c.token_expiry = datetime.now() + timedelta(seconds=20)
    monitor = vm.VaultHealthMonitor(
        c,
        token_warning_threshold=30,
        on_token_expiry_warning=lambda: called.__setitem__("n", 1),
    )
    await monitor._check_token_expiry()
    assert called["n"] == 1
    assert monitor._token_warning_sent is True
    assert expiry.sets[-1] > 0

    c.token_expiry = datetime.now() + timedelta(seconds=300)
    await monitor._check_token_expiry()
    assert monitor._token_warning_sent is False


@pytest.mark.asyncio
async def test_check_token_expiry_expired_sets_zero(metric_mocks):
    expiry, *_ = metric_mocks
    c = _Client()
    c.token_expiry = datetime.now() - timedelta(seconds=1)
    monitor = vm.VaultHealthMonitor(c)
    await monitor._check_token_expiry()
    assert expiry.sets[-1] == 0
    assert monitor._token_warning_sent is True


def test_get_status(metric_mocks):
    c = _Client()
    monitor = vm.VaultHealthMonitor(c, check_interval=5)
    status = monitor.get_status()
    assert status["running"] is False
    assert status["check_interval"] == 5


@pytest.mark.asyncio
async def test_start_when_running_noop(metric_mocks):
    c = _Client()
    monitor = vm.VaultHealthMonitor(c)
    monitor._running = True
    await monitor.start()
    assert monitor._running is True


@pytest.mark.asyncio
async def test_start_creates_background_task(metric_mocks, monkeypatch):
    c = _Client()
    monitor = vm.VaultHealthMonitor(c, check_interval=3)
    created = {}

    class _DummyTask:
        def cancel(self):
            return None

        def __await__(self):
            if False:
                yield
            return

    def _create_task(coro):
        created["coro"] = coro
        return _DummyTask()

    monkeypatch.setattr(vm.asyncio, "create_task", _create_task)
    await monitor.start()

    assert monitor._running is True
    assert isinstance(monitor._task, _DummyTask)
    assert "coro" in created
    monitor._task.cancel()
    await monitor._task
    created["coro"].close()


@pytest.mark.asyncio
async def test_stop_when_not_running_is_noop(metric_mocks):
    c = _Client()
    monitor = vm.VaultHealthMonitor(c)
    sentinel = object()
    monitor._running = False
    monitor._task = sentinel

    await monitor.stop()

    assert monitor._task is sentinel


@pytest.mark.asyncio
async def test_stop_cancels_task(metric_mocks):
    c = _Client()
    monitor = vm.VaultHealthMonitor(c)

    class DummyTask:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True

        def __await__(self):
            if False:
                yield
            raise asyncio.CancelledError

    monitor._running = True
    monitor._task = DummyTask()
    await monitor.stop()
    assert monitor._running is False
    assert monitor._task is None


@pytest.mark.asyncio
async def test_health_check_loop_handles_generic_error(metric_mocks, monkeypatch):
    _, _, failures, _, _ = metric_mocks
    c = _Client()
    monitor = vm.VaultHealthMonitor(c, check_interval=7)
    sleeps = []

    async def _boom():
        raise RuntimeError("loop-fail")

    async def _sleep(delay):
        sleeps.append(delay)
        monitor._running = False

    monkeypatch.setattr(monitor, "_perform_health_check", _boom)
    monkeypatch.setattr(vm.asyncio, "sleep", _sleep)

    monitor._running = True
    await monitor._health_check_loop()

    assert failures.incs[-1] == 1
    assert sleeps == [7]


@pytest.mark.asyncio
async def test_health_check_loop_success_path_sleeps(metric_mocks, monkeypatch):
    c = _Client()
    monitor = vm.VaultHealthMonitor(c, check_interval=4)
    calls = {"performed": 0, "sleeps": []}

    async def _ok():
        calls["performed"] += 1

    async def _sleep(delay):
        calls["sleeps"].append(delay)
        monitor._running = False

    monkeypatch.setattr(monitor, "_perform_health_check", _ok)
    monkeypatch.setattr(vm.asyncio, "sleep", _sleep)
    monitor._running = True

    await monitor._health_check_loop()

    assert calls["performed"] == 1
    assert calls["sleeps"] == [4]


@pytest.mark.asyncio
async def test_health_check_loop_propagates_cancelled(metric_mocks, monkeypatch):
    c = _Client()
    monitor = vm.VaultHealthMonitor(c)

    async def _cancel():
        raise asyncio.CancelledError()

    monkeypatch.setattr(monitor, "_perform_health_check", _cancel)
    monitor._running = True

    with pytest.raises(asyncio.CancelledError):
        await monitor._health_check_loop()


@pytest.mark.asyncio
async def test_health_change_callback_exception_handled(metric_mocks):
    c = _Client()
    c._health = False

    def _bad_callback(_is_healthy):
        raise RuntimeError("callback-failed")

    monitor = vm.VaultHealthMonitor(c, on_health_change=_bad_callback)
    monitor._last_health = True

    await monitor._perform_health_check()

    assert monitor._last_health is False


@pytest.mark.asyncio
async def test_health_restored_path(metric_mocks):
    c = _Client()
    c._health = True
    monitor = vm.VaultHealthMonitor(c)
    monitor._last_health = False

    await monitor._perform_health_check()

    assert monitor._last_health is True


@pytest.mark.asyncio
async def test_token_warning_callback_exception_handled(metric_mocks):
    c = _Client()
    c.token_expiry = datetime.now() + timedelta(seconds=5)

    def _bad_warning():
        raise RuntimeError("warn-callback-failed")

    monitor = vm.VaultHealthMonitor(
        c, token_warning_threshold=10, on_token_expiry_warning=_bad_warning
    )
    await monitor._check_token_expiry()

    assert monitor._token_warning_sent is True


def test_metrics_reporter_prometheus(metric_mocks, monkeypatch):
    c = _Client()
    reporter = vm.VaultMetricsReporter(c)
    monkeypatch.setattr(vm.prom, "generate_latest", lambda _r: b"m 1\n")
    assert reporter.get_prometheus_metrics() == "m 1\n"


@pytest.mark.asyncio
async def test_metrics_reporter_health_summary_and_checks(metric_mocks):
    c = _Client()
    c.token_expiry = datetime.now() + timedelta(seconds=50)
    reporter = vm.VaultMetricsReporter(c)
    summary = await reporter.get_health_summary()
    assert summary["vault_addr"] == "http://vault"
    assert summary["token_expires_in_seconds"] > 0
    assert await reporter.check_readiness() is True
    assert await reporter.check_liveness() is True

    c.authenticated = False
    assert await reporter.check_readiness() is False
    c.authenticated = True
    c.is_degraded = True
    assert await reporter.check_readiness() is False
    c.is_degraded = False
    c.token_expiry = datetime.now() - timedelta(seconds=1)
    assert await reporter.check_readiness() is False
    c.client = None
    assert await reporter.check_liveness() is False
