import os
from pathlib import Path

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.proxy_config_manager import (Environment, ProxyConfigManager,
                                              ProxyInfrastructureConfig,
                                              ProxyProviderConfig,
                                              SecureCredentialStore,
                                              SelectionAlgorithmConfig)


def test_selection_weights_validation() -> None:
    ok = SelectionAlgorithmConfig()
    assert ok.validate() == []
    bad = SelectionAlgorithmConfig(
        latency_weight=0.8,
        success_weight=0.4,
        stability_weight=0.2,
        geographic_weight=0.1,
    )
    assert bad.validate()


def test_infrastructure_validation_and_dict() -> None:
    cfg = ProxyInfrastructureConfig(environment=Environment.DEVELOPMENT, providers=[])
    errs = cfg.validate()
    assert any("At least one provider" in e for e in errs)
    cfg.providers.append(
        ProxyProviderConfig(name="p1", host_template="host", regions=["us"])
    )
    assert cfg.validate() == []
    d = cfg.to_dict()
    assert d["environment"] == "development"
    assert "jwt_secret" not in d["security"]


def test_credential_store_encrypt_decrypt_cache() -> None:
    store = SecureCredentialStore(master_key="test-key")
    enc = store.encrypt("secret")
    assert enc != "secret"
    dec = store.decrypt(enc)
    assert dec == "secret"
    # second read from cache should still be consistent
    assert store.decrypt(enc) == "secret"
    store.clear_cache()
    assert store._cache == {}


def test_manager_hash_and_provider_proxy_generation(tmp_path: Path) -> None:
    mgr = ProxyConfigManager(
        config_path=str(tmp_path / "config.yaml"), environment=Environment.DEVELOPMENT
    )
    assert mgr._compute_hash("abc") == mgr._compute_hash("abc")
    mgr.config.providers = [
        ProxyProviderConfig(
            name="prov",
            host_template="proxy.example",
            port=8080,
            regions=["us", "de"],
            username="u",
            password="p",
        )
    ]
    proxies = mgr.get_provider_proxies()
    assert len(proxies) == 2
    assert proxies[0].id.startswith("prov-")
