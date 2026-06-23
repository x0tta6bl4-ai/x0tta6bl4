import os
import sys
import types
import json
import importlib
from types import SimpleNamespace

import pytest

from src.coordination.events import EventBus, EventType

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


def _clear_proxy_control_plane_identity(monkeypatch):
    for name in (
        "PROXY_CONTROL_PLANE_SPIFFE_ID",
        "PROXY_CONTROL_PLANE_DID",
        "PROXY_CONTROL_PLANE_WALLET_ADDRESS",
        "X0TTA6BL4_SERVICE_SPIFFE_ID",
        "X0TTA6BL4_SERVICE_DID",
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "SERVICE_SPIFFE_ID",
        "SERVICE_DID",
        "SERVICE_WALLET_ADDRESS",
        "SPIFFE_ID",
        "DID",
        "GHOST_WALLET_ADDRESS",
    ):
        monkeypatch.delenv(name, raising=False)


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
    mod = importlib.import_module("src.network.proxy_control_plane")

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


def test_proxy_control_plane_init_without_cors_dependency():
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")
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
        with pytest.raises(AttributeError):
            mod.ProxyControlPlane(manager)
    finally:
        mod.aiohttp_cors = original_cors


@pytest.mark.asyncio
async def test_list_and_get_proxy_endpoints_filters_and_404():
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")
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
async def test_health_and_list_publish_redacted_control_plane_evidence(
    tmp_path,
    monkeypatch,
):
    _clear_proxy_control_plane_identity(monkeypatch)
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")
    bus = EventBus(project_root=str(tmp_path))
    healthy_us = _make_proxy(mod, "proxy-secret-1", region="us")
    banned_de = _make_proxy(
        mod,
        "proxy-secret-2",
        region="de",
        status=mod.ProxyStatus.BANNED,
    )
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
    plane = mod.ProxyControlPlane(manager, event_bus=bus)

    health = await plane.health_check(_make_request())
    list_resp = await plane.list_proxies(
        _make_request(query={"status": "banned", "region": "de"})
    )

    assert json.loads(health.text)["evidence"]["event_id"]
    assert json.loads(list_resp.text)["evidence"]["event_id"]
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="proxy-control-plane",
    )
    assert [event.data["operation"] for event in events] == [
        "health_check",
        "list_proxies",
    ]
    health_payload = events[0].data
    list_payload = events[1].data
    assert health_payload["component"] == "network.proxy_control_plane"
    assert health_payload["service_name"] == "proxy-control-plane"
    assert health_payload["layer"] == "network_proxy_control_plane_observed_state"
    assert health_payload["proxy_counts"] == {
        "total": 2,
        "healthy": 1,
        "degraded": 0,
        "unhealthy": 0,
        "banned": 1,
    }
    assert health_payload["service_identity_present"] == {
        "spiffe_id": False,
        "did": False,
        "wallet_address": False,
    }
    assert list_payload["status_filter"] == "banned"
    assert list_payload["region_filter_hash"].startswith("sha256:")
    assert list_payload["returned_count"] == 1
    assert "customer traffic delivery" in list_payload["claim_boundary"]
    text = str(events)
    assert "proxy-secret" not in text
    assert "127.0.0.1" not in text


@pytest.mark.asyncio
async def test_proxy_request_requires_url_and_success_path():
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")
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
async def test_proxy_request_publishes_redacted_control_plane_evidence(
    tmp_path,
    monkeypatch,
):
    _clear_proxy_control_plane_identity(monkeypatch)
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")
    bus = EventBus(project_root=str(tmp_path))
    proxy = _make_proxy(mod, "proxy-secret-1")

    class _FakeResponse:
        status = 200
        headers = {"Authorization": "secret-response-header"}
        proxy_id = "proxy-secret-1"

        async def text(self):
            return "response-body-secret"

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

    plane = mod.ProxyControlPlane(_Manager(), event_bus=bus)

    response = await plane.proxy_request(
        _make_request(
            payload={
                "url": "https://secret.example/path",
                "method": "POST",
                "headers": {"Authorization": "secret-request-header"},
                "body": "request-body-secret",
                "target_domain": "secret.example",
                "preferred_region": "de",
            }
        )
    )

    body = json.loads(response.text)
    assert body["evidence"]["event_id"]
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="proxy-control-plane",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["operation"] == "proxy_request"
    assert payload["success"] is True
    assert payload["url_hash"].startswith("sha256:")
    assert payload["target_domain_hash"].startswith("sha256:")
    assert payload["preferred_region_hash"].startswith("sha256:")
    assert payload["method"] == "POST"
    assert payload["headers_present"] is True
    assert payload["body_present"] is True
    assert payload["response"] == {
        "status_code": 200,
        "headers_count": 1,
        "body_truncated_to": 10000,
        "body_returned_chars": len("response-body-secret"),
    }
    assert payload["proxy_used_hash"].startswith("sha256:")
    text = str(payload)
    assert "secret.example" not in text
    assert "secret-request-header" not in text
    assert "request-body-secret" not in text
    assert "secret-response-header" not in text
    assert "response-body-secret" not in text
    assert "proxy-secret-1" not in text


@pytest.mark.asyncio
async def test_add_proxy_pool_validation_and_success(monkeypatch):
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")

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
async def test_add_proxy_pool_publishes_redacted_control_action_evidence(
    tmp_path,
    monkeypatch,
):
    _clear_proxy_control_plane_identity(monkeypatch)
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")
    bus = EventBus(project_root=str(tmp_path))

    class _Manager:
        def __init__(self):
            self.proxies = []
            self.domain_reputations = {}

        def add_proxy(self, proxy):
            self.proxies.append(proxy)

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

    fake_pool = [
        _make_proxy(mod, "proxy-secret-us", region="us"),
        _make_proxy(mod, "proxy-secret-de", region="de"),
    ]
    monkeypatch.setattr(mod, "create_proxy_pool_from_provider", lambda **_kwargs: fake_pool)
    plane = mod.ProxyControlPlane(_Manager(), event_bus=bus)

    response = await plane.add_proxy_pool(
        _make_request(
            payload={
                "provider": "secret-provider",
                "username": "secret-user",
                "password": "secret-pass",
                "regions": ["us", "de"],
            }
        )
    )

    body = json.loads(response.text)
    assert body["evidence"]["event_id"]
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="proxy-control-plane",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["operation"] == "add_proxy_pool"
    assert payload["success"] is True
    assert payload["provider_hash"].startswith("sha256:")
    assert payload["username_present"] is True
    assert payload["password_present"] is True
    assert payload["regions_count"] == 2
    assert payload["added_count"] == 2
    assert all(item.startswith("sha256:") for item in payload["added_proxy_id_hashes"])
    text = str(payload)
    assert "secret-provider" not in text
    assert "secret-user" not in text
    assert "secret-pass" not in text
    assert "proxy-secret" not in text


@pytest.mark.asyncio
async def test_health_check_check_proxy_health_domains_and_metrics(monkeypatch):
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")

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
    mod = importlib.import_module("src.network.proxy_control_plane")

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
        "src.network.residential_proxy_manager"
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
    mod = importlib.import_module("src.network.proxy_control_plane")

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
        def __init__(self, **kwargs):
            assert kwargs == {"event_project_root": "."}
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
