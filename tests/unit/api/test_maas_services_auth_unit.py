"""Unit tests for AuthService bounded in-memory state behavior."""

from datetime import datetime, timedelta

from src.api.maas.services import AuthService


def test_generate_api_key_evicts_oldest_when_limit_exceeded():
    auth = AuthService(api_key_secret="test")
    auth._max_api_keys = 2

    key_1 = auth.generate_api_key("u1", "starter")
    key_2 = auth.generate_api_key("u2", "pro")
    key_3 = auth.generate_api_key("u3", "enterprise")

    assert key_1 not in auth._api_keys
    assert key_2 in auth._api_keys
    assert key_3 in auth._api_keys
    assert len(auth._api_keys) == 2


def test_validate_api_key_refreshes_lru_order():
    auth = AuthService(api_key_secret="test")
    auth._max_api_keys = 2

    key_1 = auth.generate_api_key("u1", "starter")
    key_2 = auth.generate_api_key("u2", "pro")

    validated = auth.validate_api_key(key_1)
    assert validated is not None

    key_3 = auth.generate_api_key("u3", "enterprise")

    assert key_1 in auth._api_keys
    assert key_2 not in auth._api_keys
    assert key_3 in auth._api_keys


def test_create_session_evicts_oldest_when_limit_exceeded():
    auth = AuthService(api_key_secret="test")
    auth._max_sessions = 2

    s1 = auth.create_session("u1")
    s2 = auth.create_session("u2")
    s3 = auth.create_session("u3")

    assert s1 not in auth._sessions
    assert s2 in auth._sessions
    assert s3 in auth._sessions
    assert len(auth._sessions) == 2


def test_validate_session_removes_expired_entry():
    auth = AuthService(api_key_secret="test")
    token = auth.create_session("u1")
    auth._sessions[token]["expires_at"] = (
        datetime.utcnow() - timedelta(seconds=1)
    ).isoformat()

    assert auth.validate_session(token) is None
    assert token not in auth._sessions
