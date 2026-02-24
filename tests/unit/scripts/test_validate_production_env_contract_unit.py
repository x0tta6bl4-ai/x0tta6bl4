from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "validate_production_env_contract.py"
    spec = importlib.util.spec_from_file_location("validate_production_env_contract", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load validate_production_env_contract module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _base_env() -> dict[str, str]:
    return {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "postgresql://user:secure_pass@host/db",
        "FLASK_SECRET_KEY": "flask-secret-value",
        "JWT_SECRET_KEY": "jwt-secret-value",
        "CSRF_SECRET_KEY": "csrf-secret-value",
        "OPERATOR_PRIVATE_KEY": "0xdeadbeef",
        "VPN_SERVER": "vpn.example.org",
        "VPN_PORT": "51820",
        "VPN_SESSION_TOKEN": "vpn-session-token-value",
        "MTLS_ENABLED": "true",
        "RATE_LIMIT_ENABLED": "true",
        "REQUEST_VALIDATION_ENABLED": "true",
        "DB_ENFORCE_SCHEMA": "true",
        "MAAS_LIGHT_MODE": "false",
        "X0TTA6BL4_FAIL_OPEN_STARTUP": "false",
        "X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY": "false",
    }


def test_validate_env_contract_passes_for_secure_env():
    mod = _load_module()
    errors, warnings = mod.validate_env_contract(_base_env(), strict_secrets=True)
    assert errors == []
    assert warnings == []


def test_validate_env_contract_detects_missing_required_key():
    mod = _load_module()
    env = _base_env()
    del env["DATABASE_URL"]
    errors, warnings = mod.validate_env_contract(env, strict_secrets=False)
    assert any("Missing required key: DATABASE_URL" in err for err in errors)
    assert warnings == []


def test_validate_env_contract_detects_insecure_flag_values():
    mod = _load_module()
    env = _base_env()
    env["MAAS_LIGHT_MODE"] = "true"
    env["MTLS_ENABLED"] = "false"
    errors, _warnings = mod.validate_env_contract(env, strict_secrets=False)
    assert any("MAAS_LIGHT_MODE must be false" in err for err in errors)
    assert any("MTLS_ENABLED must be true" in err for err in errors)


def test_validate_env_contract_allows_env_references_in_non_strict_mode_when_enabled():
    mod = _load_module()
    env = _base_env()
    env["FLASK_SECRET_KEY"] = "${FLASK_SECRET_KEY}"
    errors, warnings = mod.validate_env_contract(
        env,
        strict_secrets=False,
        allow_env_references=True,
    )
    assert errors == []
    assert warnings == []


def test_validate_env_contract_warns_on_non_env_reference_placeholders_in_non_strict_mode():
    mod = _load_module()
    env = _base_env()
    env["FLASK_SECRET_KEY"] = "change_me"
    errors, warnings = mod.validate_env_contract(
        env,
        strict_secrets=False,
        allow_env_references=True,
    )
    assert errors == []
    assert any("FLASK_SECRET_KEY looks like a placeholder value" in msg for msg in warnings)


def test_validate_env_contract_rejects_secret_placeholders_in_strict_mode():
    mod = _load_module()
    env = _base_env()
    env["JWT_SECRET_KEY"] = "${JWT_SECRET_KEY}"
    errors, warnings = mod.validate_env_contract(env, strict_secrets=True)
    assert any("JWT_SECRET_KEY looks like a placeholder value" in err for err in errors)
    assert warnings == []


def test_parse_env_file_handles_inline_comments_and_export(tmp_path):
    mod = _load_module()
    env_file = tmp_path / "prod.env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "export ENVIRONMENT=production",
                "MTLS_ENABLED=true # keep enabled",
                "JWT_SECRET_KEY='secret-value'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    parsed = mod.parse_env_file(env_file)
    assert parsed["ENVIRONMENT"] == "production"
    assert parsed["MTLS_ENABLED"] == "true"
    assert parsed["JWT_SECRET_KEY"] == "secret-value"


def test_collect_process_env_contains_set_values(monkeypatch):
    mod = _load_module()
    monkeypatch.setenv("ENVIRONMENT", "production")
    env = mod.collect_process_env()
    assert env["ENVIRONMENT"] == "production"
