from __future__ import annotations

import hashlib

import pytest

from src.network.transport.session_manager import SessionPersistence


def test_session_persistence_uses_ephemeral_secret_without_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GHOST_NODE_SECRET", raising=False)
    monkeypatch.delenv("X0TTA6BL4_PRODUCTION", raising=False)

    manager = SessionPersistence(storage_path=str(tmp_path / "sessions.bin"))

    assert len(manager.master_secret) == 32
    assert manager.master_secret != b"fallback_entropy_!!!!".ljust(32, b"\0")


def test_session_persistence_requires_secret_in_production(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GHOST_NODE_SECRET", raising=False)
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")

    with pytest.raises(RuntimeError, match="GHOST_NODE_SECRET is required"):
        SessionPersistence(storage_path=str(tmp_path / "sessions.bin"))


def test_session_persistence_keeps_env_secret_derivation(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GHOST_NODE_SECRET", "short-secret")
    monkeypatch.setenv("X0TTA6BL4_PRODUCTION", "true")

    manager = SessionPersistence(storage_path=str(tmp_path / "sessions.bin"))

    assert manager.master_secret == b"short-secret".ljust(32, b"\0")


def test_session_persistence_prefers_pqc_identity_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GHOST_NODE_SECRET", "env-secret")
    identity_dir = tmp_path / ".tmp"
    identity_dir.mkdir()
    identity_data = b"pqc-identity-material"
    (identity_dir / "pqc_identity.txt").write_bytes(identity_data)

    manager = SessionPersistence(storage_path=str(tmp_path / "sessions.bin"))

    assert manager.master_secret == hashlib.sha256(identity_data).digest()
