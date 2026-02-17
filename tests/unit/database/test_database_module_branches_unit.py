"""Branch coverage tests for src/database/__init__.py."""

from __future__ import annotations

import runpy
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import sqlalchemy


def _database_module_path() -> Path:
    return Path(__file__).resolve().parents[3] / "src" / "database" / "__init__.py"


def _run_database_module():
    return runpy.run_path(str(_database_module_path()))


def test_postgresql_url_branch_uses_plain_create_engine(monkeypatch):
    calls = []

    def _fake_create_engine(url, **kwargs):
        calls.append((url, kwargs))
        return object()

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/x0tta6bl4")
    monkeypatch.setattr(sqlalchemy, "create_engine", _fake_create_engine)

    ns = _run_database_module()

    assert ns["DATABASE_URL"].startswith("postgresql://")
    assert calls
    assert calls[0][0].startswith("postgresql://")
    assert calls[0][1] == {}


def test_unsupported_database_url_raises_value_error(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "oracle://unsupported")
    with pytest.raises(ValueError, match="Unsupported database type"):
        _run_database_module()


def test_create_tables_calls_metadata_create_all(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x0tta6bl4.db")
    ns = _run_database_module()
    create_all = MagicMock()
    monkeypatch.setattr(ns["Base"].metadata, "create_all", create_all)

    ns["create_tables"]()

    create_all.assert_called_once_with(bind=ns["engine"])


def test_get_db_yields_session_and_closes_on_exit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./x0tta6bl4.db")
    ns = _run_database_module()

    class _Session:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    session = _Session()
    get_db = ns["get_db"]
    get_db.__globals__["SessionLocal"] = lambda: session

    gen = get_db()
    yielded = next(gen)
    assert yielded is session

    with pytest.raises(StopIteration):
        next(gen)

    assert session.closed is True
