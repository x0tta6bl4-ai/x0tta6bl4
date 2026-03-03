"""Unit tests for in-memory rate limiting in src/api/maas/auth.py."""

import pytest
from fastapi import HTTPException

from src.api.maas.auth import (UserContext, _clear_rate_limit_state,
                               check_rate_limit)


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    _clear_rate_limit_state()
    yield
    _clear_rate_limit_state()


def test_check_rate_limit_allows_within_limit(monkeypatch):
    user = UserContext(user_id="user-1", plan="pro")
    times = iter([1000.0, 1000.1, 1000.2])
    monkeypatch.setattr("src.api.maas.auth.time.monotonic", lambda: next(times))

    check_rate_limit(user, "mesh/create", requests_per_minute=3)
    check_rate_limit(user, "mesh/create", requests_per_minute=3)
    check_rate_limit(user, "mesh/create", requests_per_minute=3)


def test_check_rate_limit_blocks_when_limit_exceeded(monkeypatch):
    user = UserContext(user_id="user-2", plan="pro")
    times = iter([2000.0, 2000.1, 2000.2])
    monkeypatch.setattr("src.api.maas.auth.time.monotonic", lambda: next(times))

    check_rate_limit(user, "billing/pay", requests_per_minute=2)
    check_rate_limit(user, "billing/pay", requests_per_minute=2)

    with pytest.raises(HTTPException) as exc:
        check_rate_limit(user, "billing/pay", requests_per_minute=2)

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "59"
    assert "Rate limit exceeded" in str(exc.value.detail)


def test_check_rate_limit_isolated_by_endpoint(monkeypatch):
    user = UserContext(user_id="user-3", plan="starter")
    times = iter([3000.0, 3000.1, 3000.2, 3000.3])
    monkeypatch.setattr("src.api.maas.auth.time.monotonic", lambda: next(times))

    check_rate_limit(user, "marketplace/rent", requests_per_minute=2)
    check_rate_limit(user, "marketplace/rent", requests_per_minute=2)

    # Different endpoint should not inherit the exhausted bucket.
    check_rate_limit(user, "marketplace/release", requests_per_minute=2)


def test_check_rate_limit_isolated_by_user(monkeypatch):
    user_a = UserContext(user_id="user-a", plan="starter")
    user_b = UserContext(user_id="user-b", plan="starter")
    times = iter([4000.0, 4000.1, 4000.2])
    monkeypatch.setattr("src.api.maas.auth.time.monotonic", lambda: next(times))

    check_rate_limit(user_a, "telemetry/ingest", requests_per_minute=1)
    # Different user has an independent bucket
    check_rate_limit(user_b, "telemetry/ingest", requests_per_minute=1)


def test_check_rate_limit_allows_after_window_expires(monkeypatch):
    user = UserContext(user_id="user-4", plan="enterprise")
    times = iter([5000.0, 5061.0])
    monkeypatch.setattr("src.api.maas.auth.time.monotonic", lambda: next(times))

    check_rate_limit(user, "vision/debug", requests_per_minute=1)
    # After 61 seconds the old request leaves the window
    check_rate_limit(user, "vision/debug", requests_per_minute=1)


def test_check_rate_limit_rejects_non_positive_limits():
    user = UserContext(user_id="user-5", plan="pro")

    with pytest.raises(ValueError, match="positive integer"):
        check_rate_limit(user, "mesh/delete", requests_per_minute=0)
