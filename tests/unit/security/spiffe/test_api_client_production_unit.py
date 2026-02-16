import pytest


@pytest.mark.asyncio
async def test_workload_api_client_production_fetch_x509_svid(monkeypatch):
    mod = __import__(
        "src.security.spiffe.workload.api_client_production",
        fromlist=["WorkloadAPIClientProduction"],
    )

    # Force SDK available and patch WorkloadApiClient
    monkeypatch.setattr(mod, "SPIFFE_SDK_AVAILABLE", True)

    class _SdkSvid:
        spiffe_id = "spiffe://td/workload"
        x509_svid = b"CERT"
        x509_svid_key = b"KEY"
        bundle = [b"B1"]

        class _Exp:
            def timestamp(self):
                return 123.0

        expires_at = _Exp()

    class _Client:
        async def fetch_x509_svid(self):
            return _SdkSvid()

        async def close(self):
            return None

    monkeypatch.setattr(
        mod, "WorkloadApiClient", lambda socket_path, grpc_timeout_in_seconds: _Client()
    )

    c = mod.WorkloadAPIClientProduction(max_retries=1)
    svid = await c.fetch_x509_svid()

    assert svid.spiffe_id == "spiffe://td/workload"
    assert svid.cert_pem == b"CERT"
    assert svid.private_key_pem == b"KEY"
    assert svid.cert_chain == [b"B1"]
    assert c.current_svid is svid


@pytest.mark.asyncio
async def test_workload_api_client_production_validate_jwt_svid_missing_sub(
    monkeypatch,
):
    mod = __import__(
        "src.security.spiffe.workload.api_client_production",
        fromlist=["WorkloadAPIClientProduction"],
    )

    monkeypatch.setattr(mod, "SPIFFE_SDK_AVAILABLE", True)

    class _Client:
        async def fetch_jwt_bundles(self):
            return {}

        async def close(self):
            return None

    monkeypatch.setattr(
        mod, "WorkloadApiClient", lambda socket_path, grpc_timeout_in_seconds: _Client()
    )

    class _JWT:
        @staticmethod
        def get_unverified_header(token):
            return {}

        @staticmethod
        def get_unverified_claims(token):
            return {}

    monkeypatch.setattr(mod, "jwt", _JWT)

    c = mod.WorkloadAPIClientProduction(max_retries=1)

    ok = await c.validate_jwt_svid("t", audience=["a"])
    assert ok is False
