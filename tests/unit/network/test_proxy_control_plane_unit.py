import importlib
import os
import sys
import types
from types import SimpleNamespace

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


def test_proxy_control_plane_import_and_init():
    _install_aiohttp_cors_stub()
    mod = importlib.import_module("src.network.proxy_control_plane")

    proxy = SimpleNamespace(
        id="p1",
        host="127.0.0.1",
        port=8080,
        region="us",
        country_code="US",
        status=mod.ProxyStatus.HEALTHY,
        response_time_ms=10.0,
        success_count=1,
        failure_count=0,
        ban_count=0,
        last_check=0.0,
        city=None,
        isp=None,
        get_requests_in_last_minute=lambda: 0,
    )
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
