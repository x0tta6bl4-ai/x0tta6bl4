import ssl
from datetime import datetime, timedelta

import pytest


@pytest.mark.asyncio
async def test_spire_health_checker_server_and_agent(monkeypatch, tmp_path):
    from src.security.spiffe.production_integration import (SPIREConfig,
                                                            SPIREHealthChecker)

    cfg = SPIREConfig()
    cfg.server_address = "spire-server:8081"
    cfg.workload_socket = str(tmp_path / "api.sock")

    # mock httpx.AsyncClient
    class _Resp:
        status_code = 200

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url):
            assert url == f"http://{cfg.server_address}/health"
            return _Resp()

    monkeypatch.setattr(
        "src.security.spiffe.production_integration.httpx.AsyncClient",
        lambda timeout=5: _Client(),
    )

    hc = SPIREHealthChecker(cfg)

    assert await hc.check_server_health() is True

    # socket absent -> unhealthy
    assert await hc.check_agent_health() is False

    # create socket -> healthy
    (tmp_path / "api.sock").write_text("x")
    assert await hc.check_agent_health() is True


@pytest.mark.asyncio
async def test_svid_rotation_policy_rotates_when_below_threshold(monkeypatch):
    from src.security.spiffe.production_integration import (SPIREConfig,
                                                            SVIDRotationPolicy)

    cfg = SPIREConfig()
    cfg.cert_ttl = 100.0
    cfg.renewal_threshold = 0.8

    # create fake svid with near expiry
    class _Cert:
        @property
        def not_valid_after_utc(self):
            return datetime.utcnow() + timedelta(seconds=10)

    class _Svid:
        cert = _Cert()

    class _API:
        def __init__(self):
            self.calls = 0

        async def fetch_x509_svid(self):
            self.calls += 1
            return _Svid()

    api = _API()
    policy = SVIDRotationPolicy(cfg, api)

    await policy._check_and_rotate()

    # Called twice: initial check + rotation fetch
    assert api.calls == 2
    assert policy.rotation_count == 1
    assert policy.last_rotation is not None


@pytest.mark.asyncio
async def test_mtls_context_manager_build_context_happy_path(monkeypatch, tmp_path):
    from src.security.spiffe.production_integration import (MTLSContextManager,
                                                            SPIREConfig)

    cfg = SPIREConfig()
    cfg.min_tls_version = ssl.TLSVersion.TLSv1_3

    class _Svid:
        cert = b"CERT"
        private_key = b"KEY"

    class _API:
        async def fetch_x509_svid(self):
            return _Svid()

    # ssl context stub
    class _Ctx:
        def __init__(self):
            self.minimum_version = None
            self.ciphers = None
            self.loaded = None

        def set_ciphers(self, c):
            self.ciphers = c

        def load_cert_chain(self, cert_path, key_path):
            self.loaded = (cert_path, key_path)

    monkeypatch.setattr(
        "src.security.spiffe.production_integration.ssl.create_default_context",
        lambda purpose: _Ctx(),
    )

    # tempfiles stub
    paths = []

    class _Tmp:
        def __init__(self, name):
            self.name = str(tmp_path / name)

        def __enter__(self):
            paths.append(self.name)
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, data):
            return len(data)

    monkeypatch.setattr(
        "src.security.spiffe.production_integration.tempfile.NamedTemporaryFile",
        lambda mode, delete, suffix: _Tmp(f"f{len(paths)}{suffix}"),
    )

    unlinked = []
    monkeypatch.setattr(
        "src.security.spiffe.production_integration.Path.unlink",
        lambda self: unlinked.append(str(self)),
    )

    mgr = MTLSContextManager(cfg, _API())
    ctx = await mgr._build_context()

    assert ctx.loaded is not None
    assert len(unlinked) == 2


@pytest.mark.asyncio
async def test_production_spire_integration_status_and_health(monkeypatch):
    from src.security.spiffe.production_integration import \
        ProductionSPIREIntegration

    integ = ProductionSPIREIntegration()
    assert integ.is_healthy() is False

    class _HC:
        server_healthy = True
        agent_healthy = False

    integ.health_checker = _HC()
    assert integ.is_healthy() is False

    integ.health_checker.agent_healthy = True
    st = integ.get_status()
    assert st["initialized"] is False
    assert st["server_healthy"] is True
    assert st["agent_healthy"] is True
