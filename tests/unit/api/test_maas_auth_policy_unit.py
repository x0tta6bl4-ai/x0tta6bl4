"""
Unit tests for src/api/maas/auth.py — policy evaluation, resource matching,
and rate limiting. All tests are fast, no I/O, no network.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any, Dict

import pytest
from fastapi import HTTPException

from src.api.maas.auth import (
    UserContext,
    _clear_rate_limit_state,
    _evaluate_policy,
    _match_resource,
    check_rate_limit,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Isolate rate-limit state between tests."""
    _clear_rate_limit_state()
    yield
    _clear_rate_limit_state()


def _user(user_id: str = "u-1", plan: str = "starter") -> UserContext:
    return UserContext(user_id=user_id, plan=plan)


# ---------------------------------------------------------------------------
# _match_resource
# ---------------------------------------------------------------------------

class TestMatchResource:
    def test_exact_match(self):
        assert _match_resource("mesh/abc123", "mesh/abc123") is True

    def test_exact_mismatch(self):
        assert _match_resource("mesh/abc123", "mesh/xyz999") is False

    def test_single_wildcard_matches_segment(self):
        assert _match_resource("mesh/*", "mesh/abc123") is True

    def test_single_wildcard_does_not_match_multiple_segments(self):
        assert _match_resource("mesh/*", "mesh/abc/actions") is False

    def test_double_wildcard_matches_remaining_segments(self):
        assert _match_resource("nodes/**", "nodes/n1/actions/read") is True

    def test_double_wildcard_at_end_matches_single_segment(self):
        assert _match_resource("nodes/**", "nodes/n1") is True

    def test_wildcard_in_middle(self):
        assert _match_resource("mesh/*/nodes", "mesh/abc123/nodes") is True

    def test_wildcard_in_middle_wrong_segment_count(self):
        assert _match_resource("mesh/*/nodes", "mesh/abc123/nodes/extra") is False

    def test_pattern_longer_than_resource(self):
        assert _match_resource("mesh/abc/nodes", "mesh/abc") is False

    def test_resource_longer_than_pattern(self):
        assert _match_resource("mesh/abc", "mesh/abc/extra") is False

    def test_empty_pattern_and_resource(self):
        assert _match_resource("", "") is True

    def test_no_wildcard_no_match(self):
        assert _match_resource("mesh/abc", "mesh/xyz") is False

    def test_global_wildcard_pattern(self):
        assert _match_resource("*", "anything") is True

    def test_double_star_root_matches_deep_path(self):
        assert _match_resource("**", "a/b/c/d") is True


# ---------------------------------------------------------------------------
# _evaluate_policy
# ---------------------------------------------------------------------------

class TestEvaluatePolicy:
    def _policy(self, **kwargs) -> Dict[str, Any]:
        return {"principal": "*", "action": "*", "resource": "*", "effect": "allow", **kwargs}

    def test_wildcard_policy_allows_all(self):
        user = _user("u-1")
        policy = self._policy()
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is True

    def test_deny_effect_blocks_action(self):
        user = _user("u-1")
        policy = self._policy(effect="deny")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is False

    def test_specific_principal_matches_user(self):
        user = _user("u-1")
        policy = self._policy(principal="u-1")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is True

    def test_specific_principal_rejects_other_user(self):
        user = _user("u-2")
        policy = self._policy(principal="u-1")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is False

    def test_specific_action_matches(self):
        user = _user()
        policy = self._policy(action="read")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is True

    def test_specific_action_rejects_different_action(self):
        user = _user()
        policy = self._policy(action="write")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is False

    def test_specific_resource_matches(self):
        user = _user()
        policy = self._policy(resource="mesh/abc")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is True

    def test_specific_resource_rejects_other(self):
        user = _user()
        policy = self._policy(resource="mesh/abc")
        assert _evaluate_policy(policy, user, "read", "mesh/xyz") is False

    def test_wildcard_resource_matches_any(self):
        user = _user()
        policy = self._policy(resource="mesh/*")
        assert _evaluate_policy(policy, user, "read", "mesh/any-id") is True

    def test_all_conditions_must_match(self):
        user = _user("u-1")
        # principal matches but action does not
        policy = self._policy(principal="u-1", action="write")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is False

    def test_default_effect_is_allow(self):
        """Policy without 'effect' key defaults to allow."""
        user = _user()
        policy = {"principal": "*", "action": "*", "resource": "*"}
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is True

    def test_unknown_effect_is_deny(self):
        user = _user()
        policy = self._policy(effect="unknown-effect")
        assert _evaluate_policy(policy, user, "read", "mesh/abc") is False

    def test_wildcard_principal_matches_any_user(self):
        for uid in ("u-1", "u-2", "admin-99"):
            user = _user(uid)
            policy = self._policy(principal="*")
            assert _evaluate_policy(policy, user, "read", "mesh/abc") is True


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    def test_allows_requests_below_limit(self):
        user = _user("rl-1")
        # Should not raise for first 5 requests
        for _ in range(5):
            check_rate_limit(user, "test-endpoint", 5)

    def test_raises_429_when_limit_exceeded(self):
        user = _user("rl-2")
        for _ in range(3):
            check_rate_limit(user, "endpoint-x", 3)
        with pytest.raises(HTTPException) as exc:
            check_rate_limit(user, "endpoint-x", 3)
        assert exc.value.status_code == 429

    def test_429_includes_retry_after_header(self):
        user = _user("rl-3")
        for _ in range(2):
            check_rate_limit(user, "endpoint-y", 2)
        with pytest.raises(HTTPException) as exc:
            check_rate_limit(user, "endpoint-y", 2)
        assert "Retry-After" in exc.value.headers
        assert int(exc.value.headers["Retry-After"]) >= 1

    def test_429_detail_mentions_endpoint(self):
        user = _user("rl-4")
        ep = "mesh-deploy"
        for _ in range(1):
            check_rate_limit(user, ep, 1)
        with pytest.raises(HTTPException) as exc:
            check_rate_limit(user, ep, 1)
        assert ep in exc.value.detail

    def test_different_endpoints_have_independent_buckets(self):
        user = _user("rl-5")
        # Fill up endpoint-a
        for _ in range(2):
            check_rate_limit(user, "endpoint-a", 2)
        # endpoint-b should still be available
        check_rate_limit(user, "endpoint-b", 2)  # Should not raise

    def test_different_users_have_independent_buckets(self):
        u1 = _user("rl-6a")
        u2 = _user("rl-6b")
        # Fill up u1's bucket
        for _ in range(2):
            check_rate_limit(u1, "endpoint-z", 2)
        with pytest.raises(HTTPException):
            check_rate_limit(u1, "endpoint-z", 2)
        # u2 should not be affected
        check_rate_limit(u2, "endpoint-z", 2)  # Should not raise

    def test_raises_value_error_for_zero_limit(self):
        user = _user("rl-7")
        with pytest.raises(ValueError):
            check_rate_limit(user, "endpoint", 0)

    def test_raises_value_error_for_negative_limit(self):
        user = _user("rl-8")
        with pytest.raises(ValueError):
            check_rate_limit(user, "endpoint", -1)

    def test_anonymous_user_uses_anonymous_key(self):
        """user_id='' falls back to 'anonymous' key."""
        u1 = UserContext(user_id="", plan="starter")
        u2 = UserContext(user_id="", plan="starter")
        for _ in range(1):
            check_rate_limit(u1, "anon-ep", 1)
        # Second anonymous user shares the same bucket
        with pytest.raises(HTTPException):
            check_rate_limit(u2, "anon-ep", 1)


# ---------------------------------------------------------------------------
# UserContext properties
# ---------------------------------------------------------------------------

class TestUserContextProperties:
    def test_is_authenticated_with_user_id(self):
        u = UserContext(user_id="u-abc", plan="starter")
        assert u.is_authenticated is True

    def test_is_not_authenticated_empty_user_id(self):
        u = UserContext(user_id="", plan="starter")
        assert u.is_authenticated is False

    def test_is_enterprise_true(self):
        u = UserContext(user_id="u-1", plan="enterprise")
        assert u.is_enterprise is True

    def test_is_enterprise_false_for_pro(self):
        u = UserContext(user_id="u-1", plan="pro")
        assert u.is_enterprise is False

    def test_is_pro_true_for_pro(self):
        u = UserContext(user_id="u-1", plan="pro")
        assert u.is_pro is True

    def test_is_pro_true_for_enterprise(self):
        u = UserContext(user_id="u-1", plan="enterprise")
        assert u.is_pro is True

    def test_is_pro_false_for_starter(self):
        u = UserContext(user_id="u-1", plan="starter")
        assert u.is_pro is False

    def test_authenticated_at_defaults_to_now(self):
        from datetime import datetime
        before = datetime.utcnow()
        u = UserContext(user_id="u-1", plan="starter")
        after = datetime.utcnow()
        assert before <= u.authenticated_at <= after
