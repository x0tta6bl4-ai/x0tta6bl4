import pytest


def test_auto_renew_config_defaults():
    from src.security.spiffe.workload.auto_renew import AutoRenewConfig

    cfg = AutoRenewConfig()
    assert cfg.renewal_threshold == 0.5
    assert cfg.check_interval == 300.0


@pytest.mark.asyncio
async def test_spiffe_auto_renew_start_disabled(monkeypatch):
    from src.security.spiffe.workload import auto_renew as ar

    # Bypass import availability gating
    monkeypatch.setattr(ar, "SPIFFE_CLIENT_AVAILABLE", True)

    class _Client:
        current_svid = None
        _jwt_cache = {}

    cfg = ar.AutoRenewConfig(enabled=False)
    svc = ar.SPIFFEAutoRenew(_Client(), config=cfg)

    await svc.start()
    assert svc.is_running() is False


def test_spiffe_auto_renew_register_and_unregister_audience(monkeypatch):
    from src.security.spiffe.workload import auto_renew as ar

    monkeypatch.setattr(ar, "SPIFFE_CLIENT_AVAILABLE", True)

    class _Client:
        current_svid = None
        _jwt_cache = {}

    svc = ar.SPIFFEAutoRenew(_Client())

    svc.register_jwt_audience(["b", "a"])
    assert tuple(sorted(["a", "b"])) in svc._jwt_audiences

    svc.unregister_jwt_audience(["a", "b"])
    assert tuple(sorted(["a", "b"])) not in svc._jwt_audiences


@pytest.mark.asyncio
async def test_spiffe_auto_renew_needs_renewal_and_time_until(monkeypatch):
    from src.security.spiffe.workload import auto_renew as ar

    monkeypatch.setattr(ar, "SPIFFE_CLIENT_AVAILABLE", True)

    class _SVID:
        def __init__(self, expiry, expired=False):
            self.expiry = expiry
            self._expired = expired

        def is_expired(self):
            return self._expired

    class _Client:
        current_svid = None
        _jwt_cache = {}

    svc = ar.SPIFFEAutoRenew(
        _Client(), config=ar.AutoRenewConfig(renewal_threshold=0.5)
    )

    svid = _SVID(
        expiry=ar.datetime.utcnow() + ar.timedelta(seconds=50000), expired=False
    )
    assert svc._needs_renewal(svid) is False
    assert svc._time_until_renewal(svid) >= 0.0

    svid2 = _SVID(expiry=ar.datetime.utcnow(), expired=True)
    assert svc._needs_renewal(svid2) is True
    assert svc._time_until_renewal(svid2) == 0.0
