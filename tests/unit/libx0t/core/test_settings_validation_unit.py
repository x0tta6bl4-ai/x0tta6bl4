from __future__ import annotations

import pytest
from pydantic import ValidationError

from libx0t.core.settings import Settings


def _clear_security_env(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    monkeypatch.delenv("CSRF_SECRET_KEY", raising=False)
    monkeypatch.delenv("OPERATOR_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_requires_secrets_in_production_even_when_environment_is_from_env_file(
    monkeypatch, tmp_path
):
    _clear_security_env(monkeypatch)
    env_file = tmp_path / "prod_missing_secrets.env"
    env_file.write_text(
        "\n".join(
            [
                "ENVIRONMENT=production",
                "OPERATOR_PRIVATE_KEY=0xkey",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Secret key must be set in production"):
        Settings(_env_file=env_file)


def test_rejects_hardcoded_db_password_in_production_from_env_file(monkeypatch, tmp_path):
    _clear_security_env(monkeypatch)
    env_file = tmp_path / "prod_hardcoded_db.env"
    env_file.write_text(
        "\n".join(
            [
                "ENVIRONMENT=production",
                "FLASK_SECRET_KEY=k1",
                "JWT_SECRET_KEY=k2",
                "CSRF_SECRET_KEY=k3",
                "OPERATOR_PRIVATE_KEY=0xkey",
                "DATABASE_URL=postgresql://user:x0tta6bl4_password@host/db",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="Hardcoded database password"):
        Settings(_env_file=env_file)
