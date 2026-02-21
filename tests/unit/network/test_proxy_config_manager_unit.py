import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import src.network.proxy_config_manager as mod


def _valid_config_dict(password: str = "secret") -> dict:
    return {
        "environment": "development",
        "providers": [
            {
                "name": "prov",
                "host_template": "proxy.example",
                "port": 8080,
                "username": "u",
                "password": password,
                "regions": ["us", "de"],
            }
        ],
        "selection": {
            "strategy": "weighted_score",
            "latency_weight": 0.3,
            "success_weight": 0.4,
            "stability_weight": 0.2,
            "geographic_weight": 0.1,
        },
    }


def test_infrastructure_validate_production_and_missing_host_template(caplog):
    cfg = mod.ProxyInfrastructureConfig(
        environment=mod.Environment.PRODUCTION,
        providers=[
            mod.ProxyProviderConfig(name="broken", enabled=True, host_template="", regions=["us"])
        ],
    )
    cfg.security.api_key_required = False
    cfg.security.tls_enabled = False
    with caplog.at_level("WARNING"):
        errors = cfg.validate()
    assert any("missing host_template" in e for e in errors)
    assert any("API key required in production" in e for e in errors)
    assert "TLS not enabled in production" in caplog.text


@pytest.mark.asyncio
async def test_load_missing_file_returns_defaults(tmp_path: Path, caplog):
    mgr = mod.ProxyConfigManager(
        config_path=str(tmp_path / "missing.yaml"),
        environment=mod.Environment.DEVELOPMENT,
    )
    with caplog.at_level("WARNING"):
        cfg = await mgr.load()
    assert cfg is mgr.config
    assert "Config file not found" in caplog.text


@pytest.mark.asyncio
async def test_load_with_encrypted_password_decrypts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROXY_CONFIG_MASTER_KEY", "master-test-key")
    store = mod.SecureCredentialStore(master_key="master-test-key")
    encrypted = store.encrypt("plain-secret")

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump(_valid_config_dict(password=f"ENC:{encrypted}")))

    mgr = mod.ProxyConfigManager(
        config_path=str(cfg_path),
        environment=mod.Environment.DEVELOPMENT,
    )
    cfg = await mgr.load()

    assert cfg.providers[0].password == "plain-secret"
    assert mgr.credential_store is not None


@pytest.mark.asyncio
async def test_load_validation_error_raises(tmp_path: Path):
    cfg_path = tmp_path / "bad.yaml"
    cfg_path.write_text(
        yaml.dump(
            {
                "environment": "development",
                "providers": [],
                "selection": {
                    "latency_weight": 0.9,
                    "success_weight": 0.9,
                    "stability_weight": 0.9,
                    "geographic_weight": 0.9,
                },
            }
        )
    )
    mgr = mod.ProxyConfigManager(
        config_path=str(cfg_path),
        environment=mod.Environment.DEVELOPMENT,
    )
    with pytest.raises(ValueError):
        await mgr.load()


@pytest.mark.asyncio
async def test_save_writes_encrypted_password(tmp_path: Path):
    cfg_path = tmp_path / "config.yaml"
    mgr = mod.ProxyConfigManager(
        config_path=str(cfg_path),
        environment=mod.Environment.DEVELOPMENT,
    )
    mgr.config = mod.ProxyInfrastructureConfig(
        environment=mod.Environment.DEVELOPMENT,
        providers=[
            mod.ProxyProviderConfig(
                name="prov",
                host_template="proxy.example",
                username="u",
                password="plain-pass",
                regions=["us"],
            )
        ],
    )
    mgr.credential_store = mod.SecureCredentialStore(master_key="save-test-key")

    await mgr.save()

    saved = cfg_path.read_text()
    assert "ENC:" in saved
    assert "plain-pass" not in saved


@pytest.mark.asyncio
async def test_save_restore_backup_on_error(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text("old-content")

    mgr = mod.ProxyConfigManager(
        config_path=str(cfg_path),
        environment=mod.Environment.DEVELOPMENT,
    )
    mgr.config = mod.ProxyInfrastructureConfig(
        environment=mod.Environment.DEVELOPMENT,
        providers=[mod.ProxyProviderConfig(name="prov", host_template="proxy", regions=["us"])],
    )

    def _raise_dump(*args, **kwargs):
        raise RuntimeError("dump failed")

    monkeypatch.setattr(mod.yaml, "dump", _raise_dump)

    with pytest.raises(RuntimeError, match="dump failed"):
        await mgr.save()

    assert cfg_path.read_text() == "old-content"


def test_secure_credential_store_cache_hit(monkeypatch):
    store = mod.SecureCredentialStore(master_key="cache-hit-key")
    encrypted = store.encrypt("secret")
    assert store.decrypt(encrypted) == "secret"

    # Second read should come from cache; patched decrypt path must not be called.
    monkeypatch.setattr(
        store._cipher,
        "decrypt",
        lambda _payload: (_ for _ in ()).throw(RuntimeError("should not decrypt again")),
    )
    assert store.decrypt(encrypted) == "secret"


@pytest.mark.asyncio
async def test_watch_config_reload_and_handler_error(tmp_path: Path, monkeypatch, caplog):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump(_valid_config_dict()))

    mgr = mod.ProxyConfigManager(
        config_path=str(cfg_path),
        environment=mod.Environment.DEVELOPMENT,
    )
    mgr._running = True
    mgr._last_hash = "stale"

    state = {"loaded": 0, "handler_ok": 0, "sleep_calls": []}

    async def _fake_load():
        state["loaded"] += 1
        mgr.config = mod.ProxyInfrastructureConfig(
            environment=mod.Environment.DEVELOPMENT,
            providers=[mod.ProxyProviderConfig(name="p", host_template="h", regions=["us"])],
        )
        return mgr.config

    async def _ok_handler(_cfg):
        state["handler_ok"] += 1

    async def _bad_handler(_cfg):
        raise RuntimeError("handler boom")

    async def _sleep(seconds):
        state["sleep_calls"].append(seconds)
        mgr._running = False

    monkeypatch.setattr(mgr, "load", _fake_load)
    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)
    mgr.on_change(_ok_handler)
    mgr.on_change(_bad_handler)

    with caplog.at_level("ERROR"):
        await mgr._watch_config()

    assert state["loaded"] == 1
    assert state["handler_ok"] == 1
    assert 5 in state["sleep_calls"]
    assert "Config change handler error: handler boom" in caplog.text


@pytest.mark.asyncio
async def test_watch_config_handles_cancelled_sleep_via_error_branch(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump(_valid_config_dict()))

    mgr = mod.ProxyConfigManager(
        config_path=str(cfg_path),
        environment=mod.Environment.DEVELOPMENT,
    )
    mgr._running = True

    async def _sleep(_seconds):
        raise mod.asyncio.CancelledError()

    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)
    with pytest.raises(mod.asyncio.CancelledError):
        await mgr._watch_config()


@pytest.mark.asyncio
async def test_watch_config_handles_cancelled_sleep_via_main_loop(tmp_path: Path, monkeypatch):
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(yaml.dump(_valid_config_dict(password="plain")))

    mgr = mod.ProxyConfigManager(
        config_path=str(cfg_path),
        environment=mod.Environment.DEVELOPMENT,
    )
    mgr._running = True
    mgr._last_hash = mgr._compute_hash(cfg_path.read_text())  # no reload path

    async def _sleep(_seconds):
        raise mod.asyncio.CancelledError()

    monkeypatch.setattr(mod.asyncio, "sleep", _sleep)
    # Should break loop on CancelledError branch and return cleanly.
    await mgr._watch_config()


@pytest.mark.asyncio
async def test_start_stop_and_cache_clear(monkeypatch):
    mgr = mod.ProxyConfigManager(
        config_path="/tmp/config.yaml",
        environment=mod.Environment.DEVELOPMENT,
    )
    state = {"loaded": 0, "cancelled": False, "awaited": False}

    async def _fake_load():
        state["loaded"] += 1
        return mgr.config

    async def _await_task():
        state["awaited"] = True
        raise mod.asyncio.CancelledError()

    class _FakeTask:
        def cancel(self):
            state["cancelled"] = True

        def __await__(self):
            return _await_task().__await__()

    monkeypatch.setattr(mgr, "load", _fake_load)
    monkeypatch.setattr(mod.asyncio, "create_task", lambda coro: _FakeTask())

    mgr.credential_store = mod.SecureCredentialStore(master_key="cache-key")
    enc = mgr.credential_store.encrypt("x")
    assert mgr.credential_store.decrypt(enc) == "x"

    await mgr.start()
    assert mgr._running is True
    assert state["loaded"] == 1

    await mgr.stop()
    assert mgr._running is False
    assert state["cancelled"] is True
    assert state["awaited"] is True
    assert mgr.credential_store._cache == {}


def test_decrypt_credentials_no_store_and_error_branch(caplog):
    mgr = mod.ProxyConfigManager(config_path="/tmp/config.yaml", environment=mod.Environment.DEVELOPMENT)

    # No credential store branch should no-op.
    mgr._decrypt_credentials()

    mgr.config.providers = [
        mod.ProxyProviderConfig(name="prov", host_template="proxy.example", password="ENC:bad", regions=["us"])
    ]
    mgr.credential_store = SimpleNamespace(
        decrypt=lambda _payload: (_ for _ in ()).throw(RuntimeError("bad decrypt"))
    )
    with caplog.at_level("ERROR"):
        mgr._decrypt_credentials()
    assert "Failed to decrypt password for prov: bad decrypt" in caplog.text


def test_provider_proxy_generation_export_env_and_default_config(tmp_path: Path):
    mgr = mod.ProxyConfigManager(
        config_path=str(tmp_path / "config.yaml"),
        environment=mod.Environment.DEVELOPMENT,
    )
    mgr.config.providers = [
        mod.ProxyProviderConfig(
            name="enabled",
            enabled=True,
            host_template="proxy.example",
            port=8888,
            username="u",
            password="p",
            regions=["us", "de", "abc"],
        ),
        mod.ProxyProviderConfig(
            name="disabled",
            enabled=False,
            host_template="ignored.example",
            regions=["us"],
        ),
    ]

    proxies = mgr.get_provider_proxies()
    assert len(proxies) == 3
    assert {p.id for p in proxies} == {"enabled-us", "enabled-de", "enabled-abc"}
    assert any(p.country_code == "US" for p in proxies if p.region == "abc")

    env_path = tmp_path / ".env.proxy"
    mgr.export_env_file(str(env_path))
    env_text = env_path.read_text()
    assert "PROXY_ENV=development" in env_text
    assert "PROXY_PROVIDER_ENABLED_HOST=proxy.example" in env_text
    assert "PROXY_PROVIDER_ENABLED_REGIONS=us,de,abc" in env_text

    default_cfg = mod.create_default_config()
    assert default_cfg.environment == mod.Environment.DEVELOPMENT
    assert default_cfg.providers
    assert default_cfg.selection.strategy == "weighted_score"
