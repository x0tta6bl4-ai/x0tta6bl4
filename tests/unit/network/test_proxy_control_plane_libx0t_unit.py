import os
import sys
import types
import json
import importlib
from types import SimpleNamespace

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def _install_aiohttp_cors_stub():
    class _Cors:
        def add(self, _route):
            return None

    stub = types.SimpleNamespace(
        ResourceOptions=lambda **kwargs: kwargs,
        setup=lambda app, defaults=None: _Cors(),
    )
    sys.modules["aiohttp_cors"] = stub


def _make_proxy(mod, proxy_id: str, *, region: str = "us", status=None):
    proxy_status = status if status is not None else mod.ProxyStatus.HEALTHY
    return SimpleNamespace(
        id=proxy_id,
        host="127.0.0.1",
        port=8080,
        region=region,
        country_code=region.upper()[:2],
        status=proxy_status,
        response_time_ms=10.0,
        success_count=1,
        failure_count=0,
        ban_count=0,
        last_check=0.0,
        city=None,
        isp=None,
        get_requests_in_last_minute=lambda: 0,
    )


def _make_request(*, query=None, match_info=None, payload=None):
    async def _json():
        return payload or {}

    return SimpleNamespace(
        query=query or {},
        match_info=match_info or {},
        json=_json,
    )


class _FakeRunner:
    def __init__(self, app):
        self.app = app
        self.setup_called = False

    async def setup(self):
        self.setup_called = True


class _FakeSite:
    def __init__(self, runner, host, port):
        self.runner = runner
        self.host = host
        self.port = port
        self.started = False

    async def start(self):
        self.started = True


def test_proxy_control_plane_import_and_init():
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("libx0t.network.proxy_control_plane")

    proxy = _make_proxy(mod, "p1")
    manager = SimpleNamespace(
        proxies=[proxy],
        domain_reputations={},
        get_domain_reputation=lambda domain: SimpleNamespace(
            domain=domain,
            score=1.0,
            block_count=0,
            success_count=1,
            last_access=0.0,
        ),
        _check_proxy_health=lambda _p: None,
    )
    plane = mod.ProxyControlPlane(manager, host="127.0.0.1", port=8082)
    assert plane.host == "127.0.0.1"
    assert plane.port == 8082
    assert len(list(plane.app.router.routes())) > 0


def test_proxy_control_plane_init_without_cors_dependency(caplog):
    mod = importlib.import_module("libx0t.network.proxy_control_plane")
    original_cors = mod.aiohttp_cors
    mod.aiohttp_cors = None
    try:
        manager = SimpleNamespace(
            proxies=[],
            domain_reputations={},
            get_domain_reputation=lambda domain: SimpleNamespace(
                domain=domain,
                score=1.0,
                block_count=0,
                success_count=1,
                last_access=0.0,
            ),
            _check_proxy_health=lambda _p: None,
        )
        with caplog.at_level("WARNING"):
            plane = mod.ProxyControlPlane(manager)
        assert plane is not None
        assert "CORS is disabled" in caplog.text
    finally:
        mod.aiohttp_cors = original_cors


@pytest.mark.asyncio
async def test_list_and_get_proxy_endpoints_filters_and_404():
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("libx0t.network.proxy_control_plane")
    healthy_us = _make_proxy(mod, "p1", region="us", status=mod.ProxyStatus.HEALTHY)
    banned_de = _make_proxy(mod, "p2", region="de", status=mod.ProxyStatus.BANNED)
    manager = SimpleNamespace(
        proxies=[healthy_us, banned_de],
        domain_reputations={},
        get_domain_reputation=lambda domain: SimpleNamespace(
            domain=domain,
            score=1.0,
            block_count=0,
            success_count=1,
            last_access=0.0,
        ),
        _check_proxy_health=lambda _p: None,
    )
    plane = mod.ProxyControlPlane(manager)

    list_resp = await plane.list_proxies(
        _make_request(query={"status": "banned", "region": "de"})
    )
    list_body = json.loads(list_resp.text)
    assert [p["id"] for p in list_body["proxies"]] == ["p2"]

    get_ok = await plane.get_proxy(_make_request(match_info={"proxy_id": "p1"}))
    get_ok_body = json.loads(get_ok.text)
    assert get_ok.status == 200
    assert get_ok_body["id"] == "p1"
    assert get_ok_body["region"] == "us"

    get_missing = await plane.get_proxy(_make_request(match_info={"proxy_id": "nope"}))
    assert get_missing.status == 404
    assert "Proxy not found" in get_missing.text


@pytest.mark.asyncio
async def test_proxy_request_requires_url_and_success_path():
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("libx0t.network.proxy_control_plane")
    proxy = _make_proxy(mod, "p1")

    class _FakeResponse:
        status = 200
        headers = {"x-test": "ok"}
        proxy_id = "p1"

        async def text(self):
            return "payload"

    class _Manager:
        def __init__(self):
            self.proxies = [proxy]
            self.domain_reputations = {}

        def get_domain_reputation(self, domain):
            return SimpleNamespace(
                domain=domain,
                score=1.0,
                block_count=0,
                success_count=1,
                last_access=0.0,
            )

        async def _check_proxy_health(self, _proxy):
            return None

        async def request(self, **_kwargs):
            return _FakeResponse()

    plane = mod.ProxyControlPlane(_Manager())

    bad = await plane.proxy_request(_make_request(payload={"method": "GET"}))
    assert bad.status == 400
    assert "URL required" in bad.text

    ok = await plane.proxy_request(
        _make_request(payload={"url": "https://example.com", "method": "GET"})
    )
    ok_body = json.loads(ok.text)
    assert ok.status == 200
    assert ok_body["status"] == 200
    assert ok_body["proxy_used"] == "p1"
    assert ok_body["body"] == "payload"


@pytest.mark.asyncio
async def test_add_proxy_pool_validation_and_success(monkeypatch):
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("libx0t.network.proxy_control_plane")

    class _Manager:
        def __init__(self):
            self.proxies = []
            self.domain_reputations = {}
            self.added = []

        def add_proxy(self, proxy):
            self.proxies.append(proxy)
            self.added.append(proxy.id)

        def get_domain_reputation(self, domain):
            return SimpleNamespace(
                domain=domain,
                score=1.0,
                block_count=0,
                success_count=1,
                last_access=0.0,
            )

        async def _check_proxy_health(self, _proxy):
            return None

    manager = _Manager()
    plane = mod.ProxyControlPlane(manager)

    bad = await plane.add_proxy_pool(_make_request(payload={"provider": "p"}))
    assert bad.status == 400
    assert "provider, username, and password required" in bad.text

    fake_pool = [
        _make_proxy(mod, "p-us", region="us"),
        _make_proxy(mod, "p-de", region="de"),
    ]
    monkeypatch.setattr(mod, "create_proxy_pool_from_provider", lambda **_kwargs: fake_pool)

    ok = await plane.add_proxy_pool(
        _make_request(
            payload={
                "provider": "example",
                "username": "u",
                "password": "p",
                "regions": ["us", "de"],
            }
        )
    )
    ok_body = json.loads(ok.text)
    assert ok.status == 200
    assert ok_body["added"] == 2
    assert set(manager.added) == {"p-us", "p-de"}


@pytest.mark.asyncio
async def test_health_check_check_proxy_health_domains_and_metrics(monkeypatch):
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("libx0t.network.proxy_control_plane")

    healthy = _make_proxy(mod, "h", status=mod.ProxyStatus.HEALTHY, region="us")
    degraded = _make_proxy(mod, "d", status=mod.ProxyStatus.DEGRADED, region="de")
    unhealthy = _make_proxy(mod, "u", status=mod.ProxyStatus.UNHEALTHY, region="fr")
    banned = _make_proxy(mod, "b", status=mod.ProxyStatus.BANNED, region="jp")
    healthy.success_count = 5
    healthy.failure_count = 1
    healthy.response_time_ms = 100
    degraded.success_count = 2
    degraded.failure_count = 2
    degraded.response_time_ms = 300
    unhealthy.success_count = 0
    unhealthy.failure_count = 3
    unhealthy.response_time_ms = 900
    banned.success_count = 0
    banned.failure_count = 4
    banned.response_time_ms = 1200

    domains = {
        "good.com": SimpleNamespace(
            domain="good.com",
            score=0.9,
            block_count=0,
            success_count=10,
            last_access=1.0,
        ),
        "bad.com": SimpleNamespace(
            domain="bad.com",
            score=0.2,
            block_count=5,
            success_count=1,
            last_access=2.0,
        ),
    }

    checked = {"proxy_id": None}

    async def _check_proxy_health(proxy):
        checked["proxy_id"] = proxy.id

    manager = SimpleNamespace(
        proxies=[healthy, degraded, unhealthy, banned],
        domain_reputations=domains,
        get_domain_reputation=lambda d: domains[d],
        _check_proxy_health=_check_proxy_health,
    )
    plane = mod.ProxyControlPlane(manager)

    health = await plane.health_check(_make_request())
    health_body = json.loads(health.text)
    assert health_body["status"] == "healthy"
    assert health_body["proxies"]["healthy"] == 1
    assert health_body["proxies"]["unhealthy"] == 1
    assert health_body["proxies"]["banned"] == 1

    checked_resp = await plane.check_proxy_health(_make_request(match_info={"proxy_id": "h"}))
    checked_body = json.loads(checked_resp.text)
    assert checked_body["proxy_id"] == "h"
    assert checked["proxy_id"] == "h"

    missing_checked = await plane.check_proxy_health(
        _make_request(match_info={"proxy_id": "nope"})
    )
    assert missing_checked.status == 404

    domains_resp = await plane.list_domains(_make_request(query={"min_score": "0.5"}))
    domains_body = json.loads(domains_resp.text)
    assert [d["domain"] for d in domains_body["domains"]] == ["good.com"]

    one_domain = await plane.get_domain_reputation(
        _make_request(match_info={"domain": "bad.com"})
    )
    one_domain_body = json.loads(one_domain.text)
    assert one_domain_body["domain"] == "bad.com"
    assert one_domain_body["score"] == 0.2

    metrics = await plane.get_metrics(_make_request())
    metrics_body = json.loads(metrics.text)
    assert metrics_body["proxies"]["total"] == 4
    assert metrics_body["proxies"]["degraded"] == 1
    assert metrics_body["requests"]["total"] == 17
    assert metrics_body["domains"]["tracked"] == 2
    assert metrics_body["domains"]["high_risk"] == 1


@pytest.mark.asyncio
async def test_proxy_request_error_add_pool_error_and_xray_sync(monkeypatch):
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("libx0t.network.proxy_control_plane")

    class _Manager:
        def __init__(self):
            self.proxies = [_make_proxy(mod, "p1")]
            self.domain_reputations = {}

        def get_domain_reputation(self, domain):
            return SimpleNamespace(
                domain=domain,
                score=1.0,
                block_count=0,
                success_count=1,
                last_access=0.0,
            )

        async def _check_proxy_health(self, _proxy):
            return None

        async def request(self, **_kwargs):
            raise RuntimeError("proxy failure")

        def add_proxy(self, _proxy):
            return None

    manager = _Manager()
    plane = mod.ProxyControlPlane(manager)

    req_error = await plane.proxy_request(
        _make_request(payload={"url": "https://example.com"})
    )
    assert req_error.status == 500
    assert "proxy failure" in req_error.text

    monkeypatch.setattr(
        mod,
        "create_proxy_pool_from_provider",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider fail")),
    )
    add_error = await plane.add_proxy_pool(
        _make_request(payload={"provider": "x", "username": "u", "password": "p"})
    )
    assert add_error.status == 500
    assert "provider fail" in add_error.text

    class _Integration:
        def __init__(self, proxy_manager):
            self.proxy_manager = proxy_manager

        async def update_xray_config(self, target_domains):
            if target_domains == ["boom.com"]:
                raise RuntimeError("sync boom")

    residential_mod = importlib.import_module(
        "libx0t.network.residential_proxy_manager"
    )
    monkeypatch.setattr(
        residential_mod, "XrayResidentialIntegration", _Integration, raising=False
    )

    sync_ok = await plane.sync_xray_config(
        _make_request(payload={"target_domains": ["ok.com"]})
    )
    sync_ok_body = json.loads(sync_ok.text)
    assert sync_ok_body["status"] == "synced"
    assert sync_ok_body["domains"] == ["ok.com"]

    sync_bad = await plane.sync_xray_config(
        _make_request(payload={"target_domains": ["boom.com"]})
    )
    assert sync_bad.status == 500
    assert "sync boom" in sync_bad.text


@pytest.mark.asyncio
async def test_start_stop_and_main(monkeypatch):
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("libx0t.network.proxy_control_plane")

    manager = SimpleNamespace(
        proxies=[],
        domain_reputations={},
        get_domain_reputation=lambda d: SimpleNamespace(
            domain=d, score=1.0, block_count=0, success_count=1, last_access=0.0
        ),
        _check_proxy_health=lambda _p: None,
    )
    plane = mod.ProxyControlPlane(manager, host="127.0.0.1", port=8090)

    monkeypatch.setattr(mod.web, "AppRunner", _FakeRunner)
    monkeypatch.setattr(mod.web, "TCPSite", _FakeSite)

    shutdown_called = {"shutdown": 0, "cleanup": 0}

    async def _shutdown():
        shutdown_called["shutdown"] += 1

    async def _cleanup():
        shutdown_called["cleanup"] += 1

    plane.app.shutdown = _shutdown
    plane.app.cleanup = _cleanup

    await plane.start()
    await plane.stop()
    assert shutdown_called["shutdown"] == 1
    assert shutdown_called["cleanup"] == 1

    # main() path with KeyboardInterrupt branch and finally cleanup
    state = {"manager_start": 0, "manager_stop": 0, "cp_start": 0, "cp_stop": 0}

    class _MainManager:
        def __init__(self):
            self.proxies = []
            self.domain_reputations = {}

        async def start(self):
            state["manager_start"] += 1

        async def stop(self):
            state["manager_stop"] += 1

    class _MainCP:
        def __init__(self, manager):
            self.manager = manager

        async def start(self):
            state["cp_start"] += 1

        async def stop(self):
            state["cp_stop"] += 1

    async def _sleep(_seconds):
        raise KeyboardInterrupt()

    monkeypatch.setattr(mod, "ResidentialProxyManager", _MainManager)
    monkeypatch.setattr(mod, "ProxyControlPlane", _MainCP)
    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)

    await mod.main()
    assert state == {
        "manager_start": 1,
        "manager_stop": 1,
        "cp_start": 1,
        "cp_stop": 1,
    }
