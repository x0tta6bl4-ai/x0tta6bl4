from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "check_db_bootstrap_chain.py"
    spec = importlib.util.spec_from_file_location("check_db_bootstrap_chain", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load check_db_bootstrap_chain module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_quote_ident_escapes_quotes():
    mod = _load_module()
    assert mod._quote_ident('bad"name') == '"bad""name"'  # noqa: SLF001


def test_build_postgres_urls_sets_temp_database():
    mod = _load_module()
    admin_url, temp_url = mod._build_postgres_urls(  # noqa: SLF001
        "postgresql://user:pass@localhost:5432/postgres",
        "temp_db_name",
    )

    assert admin_url.database == "postgres"
    assert temp_url.database == "temp_db_name"


def test_build_postgres_urls_rejects_non_postgres_dsn():
    mod = _load_module()
    try:
        mod._build_postgres_urls("sqlite:///tmp.db", "temp_db")  # noqa: SLF001
    except ValueError as exc:
        assert "postgresql://" in str(exc)
    else:  # pragma: no cover - explicit failure path
        raise AssertionError("Expected ValueError for non-postgres DSN")


def test_main_skips_postgres_when_not_configured(monkeypatch):
    mod = _load_module()

    calls: list[str] = []

    def _fake_sqlite_bootstrap(
        *,
        timeout: int,
        validate_downgrade: bool = False,
        downgrade_steps: int = 1,
    ):
        calls.append(
            f"sqlite:{timeout}:{validate_downgrade}:{downgrade_steps}"
        )

    def _fake_postgres_bootstrap(
        _url: str,
        *,
        timeout: int,
        validate_downgrade: bool = False,
        downgrade_steps: int = 1,
    ):
        calls.append(
            f"postgres:{timeout}:{validate_downgrade}:{downgrade_steps}"
        )

    monkeypatch.setattr(mod, "run_sqlite_bootstrap", _fake_sqlite_bootstrap)
    monkeypatch.setattr(mod, "run_postgres_bootstrap", _fake_postgres_bootstrap)
    monkeypatch.delenv("POSTGRES_BOOTSTRAP_DATABASE_URL", raising=False)

    exit_code = mod.main([])

    assert exit_code == 0
    assert calls == ["sqlite:300:False:1"]


def test_main_requires_postgres_when_flag_is_set(monkeypatch):
    mod = _load_module()

    monkeypatch.setattr(
        mod,
        "run_sqlite_bootstrap",
        lambda *, timeout, validate_downgrade=False, downgrade_steps=1: None,
    )
    monkeypatch.delenv("POSTGRES_BOOTSTRAP_DATABASE_URL", raising=False)

    exit_code = mod.main(["--require-postgres"])

    assert exit_code == 1


def test_main_runs_postgres_when_url_provided(monkeypatch):
    mod = _load_module()

    calls: list[str] = []

    def _fake_sqlite_bootstrap(
        *,
        timeout: int,
        validate_downgrade: bool = False,
        downgrade_steps: int = 1,
    ):
        calls.append(
            f"sqlite:{timeout}:{validate_downgrade}:{downgrade_steps}"
        )

    def _fake_postgres_bootstrap(
        url: str,
        *,
        timeout: int,
        validate_downgrade: bool = False,
        downgrade_steps: int = 1,
    ):
        calls.append(
            f"postgres:{timeout}:{validate_downgrade}:{downgrade_steps}:{url}"
        )

    monkeypatch.setattr(mod, "run_sqlite_bootstrap", _fake_sqlite_bootstrap)
    monkeypatch.setattr(mod, "run_postgres_bootstrap", _fake_postgres_bootstrap)

    dsn = "postgresql://user:pass@localhost:5432/postgres"
    exit_code = mod.main(["--postgres-url", dsn, "--timeout-seconds", "123"])

    assert exit_code == 0
    assert calls == [
        "sqlite:123:False:1",
        f"postgres:123:False:1:{dsn}",
    ]


def test_main_propagates_downgrade_roundtrip_settings(monkeypatch):
    mod = _load_module()

    calls: list[str] = []

    def _fake_sqlite_bootstrap(
        *,
        timeout: int,
        validate_downgrade: bool = False,
        downgrade_steps: int = 1,
    ):
        calls.append(
            f"sqlite:{timeout}:{validate_downgrade}:{downgrade_steps}"
        )

    monkeypatch.setattr(mod, "run_sqlite_bootstrap", _fake_sqlite_bootstrap)
    monkeypatch.delenv("POSTGRES_BOOTSTRAP_DATABASE_URL", raising=False)

    exit_code = mod.main(["--validate-downgrade", "--downgrade-steps", "2"])

    assert exit_code == 0
    assert calls == ["sqlite:300:True:2"]
