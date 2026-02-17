from __future__ import annotations

import src.config.vault_config as mod

ENV_KEYS = [
    "VAULT_ADDR",
    "VAULT_NAMESPACE",
    "VAULT_K8S_ROLE",
    "VAULT_K8S_JWT_PATH",
    "VAULT_VERIFY_CA",
    "VAULT_MAX_RETRIES",
    "VAULT_RETRY_DELAY",
    "VAULT_RETRY_BACKOFF",
    "VAULT_CACHE_TTL",
    "VAULT_TOKEN_REFRESH_THRESHOLD",
    "VAULT_MONITOR_INTERVAL",
    "VAULT_TOKEN_WARNING_THRESHOLD",
    "VAULT_MONITOR_ENABLED",
]


def _clear_vault_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_client_config_from_env_defaults(monkeypatch):
    _clear_vault_env(monkeypatch)
    cfg = mod.VaultClientConfig.from_env()

    assert cfg.vault_addr == "https://vault:8200"
    assert cfg.vault_namespace is None
    assert cfg.k8s_role == "proxy-api"
    assert cfg.k8s_jwt_path == "/var/run/secrets/kubernetes.io/serviceaccount/token"
    assert cfg.verify_ca == "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    assert cfg.max_retries == 3
    assert cfg.retry_delay == 1.0
    assert cfg.retry_backoff == 2.0
    assert cfg.cache_ttl == 3600
    assert cfg.token_refresh_threshold == 0.8


def test_client_config_from_env_overrides(monkeypatch):
    _clear_vault_env(monkeypatch)
    monkeypatch.setenv("VAULT_ADDR", "https://vault.prod:8200")
    monkeypatch.setenv("VAULT_NAMESPACE", "team-a")
    monkeypatch.setenv("VAULT_K8S_ROLE", "api-role")
    monkeypatch.setenv("VAULT_K8S_JWT_PATH", "/tmp/jwt")
    monkeypatch.setenv("VAULT_VERIFY_CA", "/tmp/ca.crt")
    monkeypatch.setenv("VAULT_MAX_RETRIES", "7")
    monkeypatch.setenv("VAULT_RETRY_DELAY", "1.5")
    monkeypatch.setenv("VAULT_RETRY_BACKOFF", "2.5")
    monkeypatch.setenv("VAULT_CACHE_TTL", "120")
    monkeypatch.setenv("VAULT_TOKEN_REFRESH_THRESHOLD", "0.65")

    cfg = mod.VaultClientConfig.from_env()

    assert cfg.vault_addr == "https://vault.prod:8200"
    assert cfg.vault_namespace == "team-a"
    assert cfg.k8s_role == "api-role"
    assert cfg.k8s_jwt_path == "/tmp/jwt"
    assert cfg.verify_ca == "/tmp/ca.crt"
    assert cfg.max_retries == 7
    assert cfg.retry_delay == 1.5
    assert cfg.retry_backoff == 2.5
    assert cfg.cache_ttl == 120
    assert cfg.token_refresh_threshold == 0.65


def test_monitor_config_from_env(monkeypatch):
    _clear_vault_env(monkeypatch)
    monkeypatch.setenv("VAULT_MONITOR_INTERVAL", "15")
    monkeypatch.setenv("VAULT_TOKEN_WARNING_THRESHOLD", "45")
    monkeypatch.setenv("VAULT_MONITOR_ENABLED", "FALSE")

    cfg = mod.VaultMonitorConfig.from_env()
    assert cfg.check_interval == 15
    assert cfg.token_warning_threshold == 45
    assert cfg.enabled is False


def test_vault_paths_helpers():
    paths = mod.VaultPaths()
    assert paths.get_database_path("users") == "secret/data/proxy/database/users"
    assert paths.get_api_key_path("stripe") == "secret/data/proxy/api-keys/stripe"
    assert (
        paths.get_certificate_path("gateway")
        == "secret/data/proxy/certificates/gateway"
    )


def test_integration_from_env_and_to_dict(monkeypatch):
    _clear_vault_env(monkeypatch)
    monkeypatch.setenv("VAULT_ADDR", "http://vault.local:8200")
    monkeypatch.setenv("VAULT_K8S_ROLE", "mesh-role")
    monkeypatch.setenv("VAULT_CACHE_TTL", "99")
    monkeypatch.setenv("VAULT_MONITOR_ENABLED", "true")

    cfg = mod.VaultIntegrationConfig.from_env()
    as_dict = cfg.to_dict()

    assert cfg.client.vault_addr == "http://vault.local:8200"
    assert cfg.client.k8s_role == "mesh-role"
    assert cfg.client.cache_ttl == 99
    assert as_dict["client"]["vault_addr"] == "http://vault.local:8200"
    assert as_dict["client"]["k8s_role"] == "mesh-role"
    assert as_dict["monitor"]["enabled"] is True
    assert as_dict["paths"]["base_path"] == "secret/data/proxy"


def test_load_vault_config_logs(monkeypatch):
    expected = mod.VaultIntegrationConfig(
        client=mod.VaultClientConfig(
            vault_addr="https://vault.example:8200",
            vault_namespace="ops",
            k8s_role="role-a",
        )
    )
    log_calls = []
    monkeypatch.setattr(
        mod.VaultIntegrationConfig,
        "from_env",
        classmethod(lambda _cls: expected),
    )
    monkeypatch.setattr(mod.logger, "info", lambda *args: log_calls.append(args))

    loaded = mod.load_vault_config()
    assert loaded is expected
    assert log_calls
    assert "Loaded Vault configuration" in log_calls[0][0]


def test_validate_vault_config_happy_path():
    cfg = mod.VaultIntegrationConfig(
        client=mod.VaultClientConfig(
            vault_addr="https://vault.good:8200",
            k8s_role="service-role",
            max_retries=0,
            cache_ttl=0,
            token_refresh_threshold=0.5,
        )
    )
    assert mod.validate_vault_config(cfg) == []


def test_validate_vault_config_with_multiple_errors():
    cfg = mod.VaultIntegrationConfig(
        client=mod.VaultClientConfig(
            vault_addr="",
            k8s_role="",
            max_retries=-1,
            cache_ttl=-5,
            token_refresh_threshold=2.0,
        )
    )
    errors = mod.validate_vault_config(cfg)

    assert "VAULT_ADDR is required" in errors
    assert "VAULT_K8S_ROLE is required" in errors
    assert "VAULT_MAX_RETRIES must be non-negative" in errors
    assert "VAULT_CACHE_TTL must be non-negative" in errors
    assert "VAULT_TOKEN_REFRESH_THRESHOLD must be between 0 and 1" in errors


def test_validate_vault_config_rejects_non_http_address():
    cfg = mod.VaultIntegrationConfig(
        client=mod.VaultClientConfig(vault_addr="ftp://vault", k8s_role="service-role")
    )
    errors = mod.validate_vault_config(cfg)
    assert "VAULT_ADDR must start with http:// or https://" in errors
