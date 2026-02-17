import os
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

import src.security.vault_client as vc

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


class _Metric:
    def __init__(self):
        self.incs = []
        self.sets = []
        self.observes = []
        self.labels_calls = []

    def inc(self, value=1):
        self.incs.append(value)

    def set(self, value):
        self.sets.append(value)

    def observe(self, value):
        self.observes.append(value)

    def labels(self, **kwargs):
        self.labels_calls.append(kwargs)
        return self


class _InlineLoop:
    async def run_in_executor(self, _executor, fn):
        return fn()


class _FakeHVACClient:
    def __init__(self):
        self.adapter = object()
        self.token = None
        self.closed = False

        self.secrets = types.SimpleNamespace(
            kv=types.SimpleNamespace(
                v2=types.SimpleNamespace(
                    read_secret_version=Mock(),
                    create_or_update_secret=Mock(),
                    delete_secret_version=Mock(),
                    list_secrets=Mock(),
                )
            )
        )
        self.sys = types.SimpleNamespace(read_health_status=Mock())

    def close(self):
        self.closed = True


def _make_client(**kwargs):
    defaults = dict(
        vault_addr="https://vault.test:8200",
        vault_namespace="ns",
        k8s_role="role",
        k8s_jwt_path="/tmp/jwt",
        verify_ca=None,
        max_retries=2,
        retry_delay=0.1,
        retry_backoff=2.0,
        cache_ttl=30,
        token_refresh_threshold=0.8,
    )
    defaults.update(kwargs)
    return vc.VaultClient(**defaults)


@pytest.fixture
def metric_mocks(monkeypatch):
    auth_latency = _Metric()
    retrieve_latency = _Metric()
    write_latency = _Metric()
    auth_failures = _Metric()
    secret_failures = _Metric()
    health = _Metric()
    cache_hits = _Metric()
    cache_misses = _Metric()

    monkeypatch.setattr(vc, "vault_auth_latency", auth_latency)
    monkeypatch.setattr(vc, "vault_secret_retrieve_latency", retrieve_latency)
    monkeypatch.setattr(vc, "vault_secret_write_latency", write_latency)
    monkeypatch.setattr(vc, "vault_auth_failures", auth_failures)
    monkeypatch.setattr(vc, "vault_secret_failures", secret_failures)
    monkeypatch.setattr(vc, "vault_health", health)
    monkeypatch.setattr(vc, "vault_cache_hits", cache_hits)
    monkeypatch.setattr(vc, "vault_cache_misses", cache_misses)
    return {
        "auth_latency": auth_latency,
        "retrieve_latency": retrieve_latency,
        "write_latency": write_latency,
        "auth_failures": auth_failures,
        "secret_failures": secret_failures,
        "health": health,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }


def test_get_or_create_metric_returns_existing_collector(monkeypatch):
    existing = types.SimpleNamespace(_name="dup_metric")
    fake_registry = types.SimpleNamespace(
        _names_to_collectors={"existing": existing}
    )
    monkeypatch.setattr(vc, "REGISTRY", fake_registry)

    called = {"n": 0}

    def _metric_class(*_args, **_kwargs):
        called["n"] += 1
        return object()

    result = vc._get_or_create_metric(_metric_class, "dup_metric", "desc")
    assert result is existing
    assert called["n"] == 0
    _metric_class()
    assert called["n"] == 1


def test_get_or_create_metric_fallback_on_registry_error(monkeypatch):
    class _BrokenMap:
        def values(self):
            raise RuntimeError("broken registry")

    fake_registry = types.SimpleNamespace(_names_to_collectors=_BrokenMap())
    monkeypatch.setattr(vc, "REGISTRY", fake_registry)

    calls = []

    def _metric_class(name, description, **kwargs):
        calls.append((name, description, kwargs))
        return {"name": name, "kwargs": kwargs}

    result = vc._get_or_create_metric(_metric_class, "m1", "desc")
    assert result["name"] == "m1"
    assert calls[-1][2].get("registry") is None
    with pytest.raises(RuntimeError):
        _BrokenMap().values()


@pytest.mark.asyncio
async def test_connect_success_and_idempotent(monkeypatch, metric_mocks):
    fake_hvac_client = _FakeHVACClient()
    fake_k8s_auth = Mock()
    client = _make_client(verify_ca="/tmp/ca.pem")

    monkeypatch.setattr(vc.hvac, "Client", lambda **_kwargs: fake_hvac_client)
    monkeypatch.setattr(vc, "Kubernetes", lambda _adapter: fake_k8s_auth)
    monkeypatch.setattr(client, "_authenticate", AsyncMock())

    await client.connect()
    assert client.client is fake_hvac_client
    assert client._k8s_auth is fake_k8s_auth
    assert client._authenticated is True
    assert client._degraded is False
    assert metric_mocks["health"].sets[-1] == 1

    called = {"n": 0}
    monkeypatch.setattr(vc.hvac, "Client", lambda **_kwargs: called.__setitem__("n", 1))
    await client.connect()
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_connect_failure_sets_degraded(monkeypatch, metric_mocks):
    client = _make_client()
    monkeypatch.setattr(
        vc.hvac, "Client", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("boom"))
    )

    with pytest.raises(vc.VaultAuthError):
        await client.connect()

    assert client._degraded is True
    assert metric_mocks["health"].sets[-1] == 0


@pytest.mark.asyncio
async def test_authenticate_success(monkeypatch, metric_mocks):
    client = _make_client()
    fake_hvac_client = _FakeHVACClient()
    client.client = fake_hvac_client
    client._k8s_auth = Mock()
    client._k8s_auth.login.return_value = {
        "auth": {"client_token": "token-123", "lease_duration": 100}
    }
    monkeypatch.setattr(client, "_read_jwt_token", AsyncMock(return_value="jwt"))

    await client._authenticate()

    assert client.token == "token-123"
    assert client.token_ttl == 100
    assert client.token_expiry is not None
    assert client.client.token == "token-123"
    assert metric_mocks["auth_latency"].observes


@pytest.mark.asyncio
async def test_authenticate_retries_then_raises(monkeypatch, metric_mocks):
    client = _make_client(max_retries=2, retry_delay=0.5, retry_backoff=2.0)
    client.client = _FakeHVACClient()
    client._k8s_auth = Mock()
    monkeypatch.setattr(
        client, "_read_jwt_token", AsyncMock(side_effect=RuntimeError("jwt fail"))
    )

    delays = []

    async def _fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(vc.asyncio, "sleep", _fake_sleep)

    with pytest.raises(vc.VaultAuthError):
        await client._authenticate()

    assert delays == [0.5]
    assert len(metric_mocks["auth_failures"].labels_calls) == 2


@pytest.mark.asyncio
async def test_read_jwt_token_success_and_errors(monkeypatch):
    client = _make_client()
    monkeypatch.setattr(vc.asyncio, "get_event_loop", lambda: _InlineLoop())

    monkeypatch.setattr(client, "_read_jwt_sync", lambda: "jwt-ok")
    assert await client._read_jwt_token() == "jwt-ok"

    monkeypatch.setattr(
        client, "_read_jwt_sync", lambda: (_ for _ in ()).throw(FileNotFoundError())
    )
    with pytest.raises(vc.VaultAuthError):
        await client._read_jwt_token()

    monkeypatch.setattr(
        client, "_read_jwt_sync", lambda: (_ for _ in ()).throw(RuntimeError("bad"))
    )
    with pytest.raises(vc.VaultAuthError):
        await client._read_jwt_token()


def test_read_jwt_sync_reads_file(tmp_path):
    token_path = tmp_path / "jwt-token"
    token_path.write_text("token\n", encoding="utf-8")
    client = _make_client(k8s_jwt_path=str(token_path))
    assert client._read_jwt_sync() == "token"


@pytest.mark.asyncio
async def test_ensure_authenticated_connect_and_refresh(monkeypatch):
    client = _make_client()

    monkeypatch.setattr(client, "connect", AsyncMock())
    await client._ensure_authenticated()
    client.connect.assert_awaited_once()

    client._authenticated = True
    client.client = _FakeHVACClient()
    client.token_expiry = datetime.now() - timedelta(seconds=1)
    monkeypatch.setattr(client, "_authenticate", AsyncMock())

    cleared = {"n": 0}
    monkeypatch.setattr(client, "_clear_cache", lambda: cleared.__setitem__("n", 1))
    await client._ensure_authenticated()
    assert cleared["n"] == 1
    client._authenticate.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_secret_key_not_found_and_cache_key_lookup(monkeypatch, metric_mocks):
    client = _make_client()
    fake_hvac_client = _FakeHVACClient()
    fake_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"k1": "v1"}}
    }
    client.client = fake_hvac_client
    monkeypatch.setattr(client, "_ensure_authenticated", AsyncMock())

    with pytest.raises(vc.VaultSecretError):
        await client.get_secret("proxy/path", secret_key="missing", use_cache=True)

    client._cache_secret("proxy/path", {"k1": "v1"})
    assert client._get_from_cache("proxy/path", "k1") == "v1"
    assert metric_mocks["cache_misses"].incs


@pytest.mark.asyncio
async def test_get_secret_connection_error_sets_degraded(monkeypatch, metric_mocks):
    client = _make_client()
    fake_hvac_client = _FakeHVACClient()
    fake_hvac_client.secrets.kv.v2.read_secret_version.side_effect = RuntimeError(
        "socket closed"
    )
    client.client = fake_hvac_client
    monkeypatch.setattr(client, "_ensure_authenticated", AsyncMock())

    with pytest.raises(vc.VaultSecretError, match="Vault unavailable: socket closed"):
        await client.get_secret("proxy/path", use_cache=False)

    assert client._degraded is True
    assert {"operation": "read", "reason": "connection_error"} in metric_mocks[
        "secret_failures"
    ].labels_calls


@pytest.mark.asyncio
async def test_put_delete_list_secret_error_paths(monkeypatch, metric_mocks):
    client = _make_client()
    fake_hvac_client = _FakeHVACClient()
    client.client = fake_hvac_client
    monkeypatch.setattr(client, "_ensure_authenticated", AsyncMock())

    fake_hvac_client.secrets.kv.v2.create_or_update_secret.side_effect = vc.VaultError(
        "write fail"
    )
    with pytest.raises(vc.VaultSecretError):
        await client.put_secret("a/b", {"x": 1})

    fake_hvac_client.secrets.kv.v2.delete_secret_version.side_effect = vc.VaultError(
        "delete fail"
    )
    with pytest.raises(vc.VaultSecretError):
        await client.delete_secret("a/b")

    fake_hvac_client.secrets.kv.v2.list_secrets.side_effect = vc.VaultError(
        "list fail"
    )
    with pytest.raises(vc.VaultSecretError):
        await client.list_secrets("a/")

    assert len(metric_mocks["secret_failures"].labels_calls) >= 2


@pytest.mark.asyncio
async def test_delete_secret_success_invalidates_cache(monkeypatch):
    client = _make_client()
    fake_hvac_client = _FakeHVACClient()
    client.client = fake_hvac_client
    monkeypatch.setattr(client, "_ensure_authenticated", AsyncMock())

    invalidated = []
    monkeypatch.setattr(client, "_invalidate_cache", lambda path: invalidated.append(path))

    await client.delete_secret("a/b")

    fake_hvac_client.secrets.kv.v2.delete_secret_version.assert_called_once_with(path="a/b")
    assert invalidated == ["a/b"]


def test_cache_expiry_and_clear_cache():
    client = _make_client(cache_ttl=1)
    client._secret_cache["p"] = {"k": "v"}
    client._cache_expiry["p"] = datetime.now() - timedelta(seconds=10)

    assert client._get_from_cache("p") is None
    assert "p" not in client._secret_cache

    client._secret_cache["x"] = {"a": 1}
    client._cache_expiry["x"] = datetime.now()
    client._clear_cache()
    assert client._secret_cache == {}
    assert client._cache_expiry == {}


@pytest.mark.asyncio
async def test_health_check_properties_stats_and_close(monkeypatch, metric_mocks):
    client = _make_client(cache_ttl=77)
    assert await client.health_check() is False

    fake_hvac_client = _FakeHVACClient()
    client.client = fake_hvac_client

    fake_hvac_client.sys.read_health_status.return_value = {
        "initialized": True,
        "sealed": False,
    }
    assert await client.health_check() is True
    assert client._degraded is False
    assert metric_mocks["health"].sets[-1] == 1

    fake_hvac_client.sys.read_health_status.return_value = {
        "initialized": True,
        "sealed": True,
    }
    assert await client.health_check() is False
    assert client._degraded is True
    assert metric_mocks["health"].sets[-1] == 0

    fake_hvac_client.sys.read_health_status.side_effect = RuntimeError("down")
    assert await client.health_check() is False
    assert client._degraded is True

    client._authenticated = True
    assert client.is_healthy is False
    assert client.is_degraded is True
    assert client.authenticated is True

    client._secret_cache["one"] = {"v": 1}
    stats = client.get_cache_stats()
    assert stats["cached_secrets"] == 1
    assert stats["cache_ttl_seconds"] == 77

    class _BrokenCloseClient(_FakeHVACClient):
        def close(self):
            raise RuntimeError("close fail")

    client.client = _BrokenCloseClient()
    client._authenticated = True
    client._secret_cache["z"] = {"v": 2}
    client._cache_expiry["z"] = datetime.now()

    await client.close()
    assert client.client is None
    assert client._k8s_auth is None
    assert client._authenticated is False
    assert client._secret_cache == {}


@pytest.mark.asyncio
async def test_close_calls_underlying_client_close():
    client = _make_client()
    fake_hvac_client = _FakeHVACClient()
    client.client = fake_hvac_client
    await client.close()
    assert fake_hvac_client.closed is True
