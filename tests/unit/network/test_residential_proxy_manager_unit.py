import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import src.network.residential_proxy_manager as mod


class _ResponseContext:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc

    async def __aenter__(self):
        if self._exc is not None:
            raise self._exc
        return self._response

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Session:
    def __init__(self, get_ctx=None, request_ctx=None):
        self._get_ctx = get_ctx or _ResponseContext(
            response=SimpleNamespace(status=200)
        )
        self._request_ctx = request_ctx or _ResponseContext(
            response=SimpleNamespace(status=200)
        )
        self.get_calls = []
        self.request_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def get(self, *args, **kwargs):
        self.get_calls.append((args, kwargs))
        return self._get_ctx

    def request(self, *args, **kwargs):
        self.request_calls.append((args, kwargs))
        return self._request_ctx


def _proxy(proxy_id: str, *, status=mod.ProxyStatus.HEALTHY, region="us"):
    return mod.ProxyEndpoint(
        id=proxy_id,
        host="proxy.example",
        port=8080,
        username="u",
        password="p",
        region=region,
        country_code=region.upper() if len(region) == 2 else "US",
        status=status,
    )


def test_proxy_endpoint_url_and_rate_limit(monkeypatch):
    p_with_auth = mod.ProxyEndpoint(
        id="p1", host="h", port=80, username="u", password="p", max_requests_per_minute=2
    )
    p_without_auth = mod.ProxyEndpoint(id="p2", host="h2", port=81)
    assert p_with_auth.to_url() == "http://u:p@h:80"
    assert p_without_auth.to_url() == "http://h2:81"

    now = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "time", lambda: now["t"])
    p_with_auth.record_request()
    now["t"] = 1010.0
    p_with_auth.record_request()
    assert p_with_auth.get_requests_in_last_minute() == 2
    assert p_with_auth.is_rate_limited() is True

    now["t"] = 1070.0
    assert p_with_auth.get_requests_in_last_minute() == 0
    assert p_with_auth.is_rate_limited() is False


def test_domain_reputation_score_updates(monkeypatch):
    rep = mod.DomainReputation(domain="example.com", score=0.9)
    now = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "time", lambda: now["t"])

    rep.update_score(True)
    assert rep.success_count == 1
    assert rep.score == 1.0

    rep.update_score(False)
    assert rep.block_count == 1
    assert rep.score == 0.8


def test_tls_fingerprint_randomizer(monkeypatch):
    randomizer = mod.TLSFingerprintRandomizer()
    monkeypatch.setattr(mod.random, "choice", lambda seq: seq[0])

    headers_first = randomizer.get_headers()
    assert "User-Agent" in headers_first

    profile = randomizer.get_random_profile()
    assert profile["name"] == "chrome_120"

    ctx = randomizer.create_ssl_context()
    assert ctx.minimum_version == mod.ssl.TLSVersion.TLSv1_2
    assert ctx.maximum_version == mod.ssl.TLSVersion.TLSv1_3

    headers = randomizer.get_headers()
    assert "User-Agent" in headers
    assert headers["Connection"] == "keep-alive"


@pytest.mark.asyncio
async def test_manager_add_start_stop_and_add_from_config(monkeypatch):
    manager = mod.ResidentialProxyManager()
    manager.add_proxy(_proxy("p1"))
    manager.add_proxies_from_config(
        [
            {
                "id": "p2",
                "host": "proxy2.example",
                "port": 8081,
                "region": "de",
                "country_code": "DE",
            }
        ]
    )
    assert len(manager.proxies) == 2

    state = {"cancelled": False, "awaited": False}

    async def _await_task():
        state["awaited"] = True
        raise mod.asyncio.CancelledError()

    class _FakeTask:
        def cancel(self):
            state["cancelled"] = True

        def __await__(self):
            return _await_task().__await__()

    monkeypatch.setattr(mod.asyncio, "create_task", lambda coro: _FakeTask())

    await manager.start()
    assert manager._running is True
    await manager.stop()
    assert manager._running is False
    assert state["cancelled"] is True
    assert state["awaited"] is True


@pytest.mark.asyncio
async def test_health_check_loop_error_branch(monkeypatch, caplog):
    manager = mod.ResidentialProxyManager(health_check_interval=1)
    manager._running = True
    state = {"calls": 0, "sleep_calls": []}

    async def _check_all():
        state["calls"] += 1
        if state["calls"] == 1:
            raise RuntimeError("health boom")
        manager._running = False

    async def _sleep(seconds):
        state["sleep_calls"].append(seconds)
        return None

    monkeypatch.setattr(manager, "_check_all_proxies", _check_all)
    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)

    with caplog.at_level("ERROR"):
        await manager._health_check_loop()

    assert state["calls"] >= 2
    assert 10 in state["sleep_calls"]
    assert "Health check error: health boom" in caplog.text


@pytest.mark.asyncio
async def test_health_check_loop_cancelled_branch(monkeypatch):
    manager = mod.ResidentialProxyManager(health_check_interval=1)
    manager._running = True

    async def _check_all():
        return None

    async def _sleep(_seconds):
        raise mod.asyncio.CancelledError()

    monkeypatch.setattr(manager, "_check_all_proxies", _check_all)
    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)
    await manager._health_check_loop()


@pytest.mark.asyncio
async def test_check_all_proxies_runs_each_proxy(monkeypatch):
    manager = mod.ResidentialProxyManager()
    manager.proxies = [_proxy("p1"), _proxy("p2"), _proxy("p3")]
    seen = []

    async def _check(proxy):
        seen.append(proxy.id)

    monkeypatch.setattr(manager, "_check_proxy_health", _check)
    await manager._check_all_proxies()
    assert set(seen) == {"p1", "p2", "p3"}


@pytest.mark.asyncio
async def test_check_proxy_health_success_and_recovery(monkeypatch):
    manager = mod.ResidentialProxyManager(max_failures=2)
    proxy = _proxy("p1", status=mod.ProxyStatus.UNHEALTHY)
    proxy.failure_count = 1

    session = _Session(get_ctx=_ResponseContext(response=SimpleNamespace(status=200)))
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session)

    now = {"t": 1000.0}
    monkeypatch.setattr(mod.time, "time", lambda: now["t"])
    await manager._check_proxy_health(proxy)

    assert proxy.success_count == 1
    assert proxy.failure_count == 0
    assert proxy.status == mod.ProxyStatus.HEALTHY
    assert proxy.last_check == 1000.0
    assert proxy.response_time_ms >= 0.0


@pytest.mark.asyncio
async def test_check_proxy_health_failure_status_and_exception(monkeypatch):
    manager = mod.ResidentialProxyManager(max_failures=1)
    proxy_non_200 = _proxy("p2")
    session_non_200 = _Session(
        get_ctx=_ResponseContext(response=SimpleNamespace(status=500))
    )
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session_non_200)
    await manager._check_proxy_health(proxy_non_200)
    assert proxy_non_200.status == mod.ProxyStatus.UNHEALTHY

    proxy_exc = _proxy("p3")
    session_exc = _Session(get_ctx=_ResponseContext(exc=RuntimeError("net fail")))
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session_exc)
    await manager._check_proxy_health(proxy_exc)
    assert proxy_exc.failure_count >= 1
    assert proxy_exc.status == mod.ProxyStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_get_domain_reputation_and_get_proxy_branches(monkeypatch, caplog):
    manager = mod.ResidentialProxyManager()
    p1 = _proxy("p1", status=mod.ProxyStatus.HEALTHY, region="us")
    p2 = _proxy("p2", status=mod.ProxyStatus.HEALTHY, region="de")
    p2.success_count = 10
    manager.proxies = [p1, p2]

    rep = manager.get_domain_reputation("x.com")
    assert rep.domain == "x.com"
    assert manager.get_domain_reputation("x.com") is rep

    # no healthy branch
    p1.status = mod.ProxyStatus.UNHEALTHY
    p2.status = mod.ProxyStatus.UNHEALTHY
    with caplog.at_level("ERROR"):
        none_proxy = await manager.get_proxy(require_healthy=True)
    assert none_proxy is None
    assert "No healthy proxies available" in caplog.text

    # rate-limited branch
    p1.status = mod.ProxyStatus.HEALTHY
    p2.status = mod.ProxyStatus.HEALTHY
    p1.is_rate_limited = lambda: True
    p2.is_rate_limited = lambda: True
    with caplog.at_level("WARNING"):
        none_limited = await manager.get_proxy(require_healthy=False)
    assert none_limited is None
    assert "All proxies rate limited" in caplog.text

    # low reputation + region filter + randomized selection disabled
    p1.is_rate_limited = lambda: False
    p2.is_rate_limited = lambda: False
    manager.get_domain_reputation("low.com").score = 0.1
    monkeypatch.setattr(mod.random, "random", lambda: 0.99)
    selected = await manager.get_proxy(
        target_domain="low.com", preferred_region="de", require_healthy=False
    )
    assert selected is not None
    assert selected.region == "de"


@pytest.mark.asyncio
async def test_get_proxy_round_robin_randomization_branch(monkeypatch):
    manager = mod.ResidentialProxyManager()
    p1 = _proxy("p1", status=mod.ProxyStatus.HEALTHY, region="us")
    p2 = _proxy("p2", status=mod.ProxyStatus.HEALTHY, region="de")
    manager.proxies = [p1, p2]

    p1.is_rate_limited = lambda: False
    p2.is_rate_limited = lambda: False

    monkeypatch.setattr(mod.random, "random", lambda: 0.1)  # enter randomization
    monkeypatch.setattr(mod.random, "randint", lambda a, b: 1)
    selected = await manager.get_proxy(require_healthy=False)
    assert selected.id == "p2"


@pytest.mark.asyncio
async def test_request_success_403_ban_and_retry(monkeypatch):
    manager = mod.ResidentialProxyManager()
    proxy = _proxy("p1")

    async def _get_proxy(*args, **kwargs):
        return proxy

    manager.get_proxy = _get_proxy
    manager.tls_randomizer.create_ssl_context = lambda: "ssl_ctx"
    manager.tls_randomizer.get_headers = lambda: {"User-Agent": "ua"}

    # success path
    session_ok = _Session(
        request_ctx=_ResponseContext(response=SimpleNamespace(status=200))
    )
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session_ok)
    response = await manager.request(
        "https://example.com/a", method="POST", headers={"X-Test": "1"}, data="payload"
    )
    assert response.status == 200
    assert manager.get_domain_reputation("example.com").success_count >= 1

    # 403 branch with ban threshold
    proxy.ban_count = 2
    session_403 = _Session(
        request_ctx=_ResponseContext(response=SimpleNamespace(status=403))
    )
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session_403)
    response_403 = await manager.request("https://example.com/b")
    assert response_403.status == 403
    assert proxy.status == mod.ProxyStatus.BANNED

    # retry then fail
    session_fail = _Session(
        request_ctx=_ResponseContext(exc=RuntimeError("request fail"))
    )
    monkeypatch.setattr(mod.aiohttp, "ClientSession", lambda: session_fail)
    sleeps = []

    async def _sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)

    with pytest.raises(RuntimeError, match="request fail"):
        await manager.request("https://example.com/c", max_retries=3)
    assert sleeps == [1, 2]


@pytest.mark.asyncio
async def test_request_raises_when_no_proxy_available():
    manager = mod.ResidentialProxyManager()

    async def _none_proxy(*args, **kwargs):
        return None

    manager.get_proxy = _none_proxy
    with pytest.raises(RuntimeError, match="No proxies available"):
        await manager.request("https://example.com/x")


@pytest.mark.asyncio
async def test_request_zero_retries_raises_max_retries_exceeded():
    manager = mod.ResidentialProxyManager()
    with pytest.raises(RuntimeError, match="Max retries exceeded"):
        await manager.request("https://example.com/x", max_retries=0)


@pytest.mark.asyncio
async def test_xray_integration_generate_and_update_config(tmp_path: Path, caplog):
    manager = mod.ResidentialProxyManager()
    healthy = _proxy("h1", status=mod.ProxyStatus.HEALTHY)
    unhealthy = _proxy("u1", status=mod.ProxyStatus.UNHEALTHY)
    manager.proxies = [healthy, unhealthy, _proxy("h2"), _proxy("h3"), _proxy("h4")]

    cfg_path = tmp_path / "xray.json"
    cfg_path.write_text(
        json.dumps(
            {
                "outbounds": [{"tag": "existing"}, {"tag": "residential-old"}],
                "routing": {"rules": [{"outboundTag": "residential-old"}, {"outboundTag": "existing"}]},
            }
        )
    )

    integration = mod.XrayResidentialIntegration(manager, xray_config_path=str(cfg_path))
    outbound = integration.generate_xray_outbound(healthy)
    assert outbound["protocol"] == "socks"
    assert outbound["tag"] == "residential-h1"
    assert outbound["settings"]["servers"][0]["users"][0]["user"] == "u"

    await integration.update_xray_config(["example.com"])
    payload = json.loads(cfg_path.read_text())
    res_outbounds = [ob for ob in payload["outbounds"] if ob["tag"].startswith("residential-")]
    assert len(res_outbounds) == 3
    assert payload["routing"]["rules"][0]["domain"] == ["example.com"]

    # no healthy branch
    manager.proxies = [_proxy("bad", status=mod.ProxyStatus.UNHEALTHY)]
    with caplog.at_level("ERROR"):
        await integration.update_xray_config(["example.com"])
    assert "No healthy proxies for Xray integration" in caplog.text


def test_create_proxy_pool_from_provider():
    pool = mod.create_proxy_pool_from_provider(
        "oxylabs", username="u", password="p", regions=["us", "gb", "abc"]
    )
    assert len(pool) == 3
    assert pool[0].id == "oxylabs-us"
    assert pool[0].host == mod.PROXY_POOL_CONFIGS["oxylabs"]["host_template"]
    assert any(p.country_code == "US" for p in pool if p.region == "abc")

    with pytest.raises(ValueError, match="Unknown provider"):
        mod.create_proxy_pool_from_provider("nope", username="u", password="p")
