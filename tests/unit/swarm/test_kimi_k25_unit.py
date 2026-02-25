"""Unit tests for KimiK25Integration (TD-007).

Tests cover:
- Disabled path returns (0, "LLM not enabled")
- No API key → heuristic fallback (no HTTP call)
- Successful LLM call parses index+reasoning correctly
- Malformed JSON response falls back to heuristic
- HTTP error triggers retry then heuristic fallback
- _parse_response handles markdown fences and edge cases
- _heuristic_fallback scoring rules
- get_stats tracks request/error counts
"""
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.swarm.intelligence import DecisionContext, DecisionType, KimiK25Integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(topic="routing", decision_type=DecisionType.ROUTING) -> DecisionContext:
    return DecisionContext(topic=topic, decision_type=decision_type)


def _integration(enabled=True, api_key="test-key", **kw) -> KimiK25Integration:
    ki = KimiK25Integration(enabled=enabled, api_endpoint="http://mock", **kw)
    ki._api_key = api_key
    return ki


def _mock_http_response(content_text: str, status_code: int = 200):
    """Return a mock httpx Response-like object."""
    body = {
        "choices": [{"message": {"content": content_text}}]
    }
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.raise_for_status = MagicMock() if status_code < 400 else MagicMock(
        side_effect=Exception(f"HTTP {status_code}")
    )
    return resp


# ---------------------------------------------------------------------------
# Disabled / no-key paths
# ---------------------------------------------------------------------------

class TestDisabledPath:
    @pytest.mark.asyncio
    async def test_disabled_returns_zero_index(self):
        ki = KimiK25Integration(enabled=False)
        idx, reason = await ki.enhance_decision(_ctx(), ["a", "b"])
        assert idx == 0

    @pytest.mark.asyncio
    async def test_disabled_returns_not_enabled_reason(self):
        ki = KimiK25Integration(enabled=False)
        _, reason = await ki.enhance_decision(_ctx(), ["a", "b"])
        assert "not enabled" in reason

    @pytest.mark.asyncio
    async def test_empty_options_returns_zero(self):
        ki = _integration()
        idx, _ = await ki.enhance_decision(_ctx(), [])
        assert idx == 0

    @pytest.mark.asyncio
    async def test_no_api_key_uses_heuristic(self):
        """No key → heuristic fallback, no HTTP call."""
        ki = KimiK25Integration(enabled=True, api_endpoint="http://mock")
        ki._api_key = ""
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(ki, "_load_httpx") as mock_load:
                idx, reason = await ki.enhance_decision(_ctx(), ["x", "y"])
        mock_load.assert_not_called()
        assert idx in (0, 1)
        assert "heuristic" in reason


# ---------------------------------------------------------------------------
# Successful LLM call
# ---------------------------------------------------------------------------

class TestSuccessfulCall:
    @pytest.mark.asyncio
    async def test_returns_llm_recommended_index(self):
        ki = _integration()
        good_json = json.dumps({"index": 1, "reasoning": "option 1 is safer"})

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_http_response(good_json))

        with patch.object(ki, "_load_httpx") as mock_load:
            mock_load.return_value = MagicMock(AsyncClient=MagicMock(return_value=mock_client))
            idx, reason = await ki.enhance_decision(_ctx(), ["opt0", "opt1", "opt2"])

        assert idx == 1
        assert "safer" in reason

    @pytest.mark.asyncio
    async def test_request_count_increments(self):
        ki = _integration()
        good_json = json.dumps({"index": 0, "reasoning": "ok"})

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_http_response(good_json))

        with patch.object(ki, "_load_httpx") as mock_load:
            mock_load.return_value = MagicMock(AsyncClient=MagicMock(return_value=mock_client))
            await ki.enhance_decision(_ctx(), ["a", "b"])

        assert ki._request_count == 1

    @pytest.mark.asyncio
    async def test_json_with_markdown_fences_parsed(self):
        ki = _integration()
        fenced = "```json\n{\"index\": 0, \"reasoning\": \"stable\"}\n```"
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_http_response(fenced))

        with patch.object(ki, "_load_httpx") as mock_load:
            mock_load.return_value = MagicMock(AsyncClient=MagicMock(return_value=mock_client))
            idx, reason = await ki.enhance_decision(_ctx(), ["a", "b"])

        assert idx == 0


# ---------------------------------------------------------------------------
# Error / fallback paths
# ---------------------------------------------------------------------------

class TestFallbackPaths:
    @pytest.mark.asyncio
    async def test_http_error_falls_back_to_heuristic(self):
        ki = _integration(max_retries=0)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("connection refused"))

        with patch.object(ki, "_load_httpx") as mock_load:
            mock_load.return_value = MagicMock(AsyncClient=MagicMock(return_value=mock_client))
            idx, reason = await ki.enhance_decision(_ctx(), ["a", "b"])

        assert "heuristic" in reason
        assert ki._error_count == 1

    @pytest.mark.asyncio
    async def test_malformed_json_falls_back(self):
        ki = _integration(max_retries=0)
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_http_response("not json at all"))

        with patch.object(ki, "_load_httpx") as mock_load:
            mock_load.return_value = MagicMock(AsyncClient=MagicMock(return_value=mock_client))
            idx, reason = await ki.enhance_decision(_ctx(), ["x", "y"])

        assert "heuristic" in reason

    @pytest.mark.asyncio
    async def test_out_of_range_index_falls_back(self):
        ki = _integration(max_retries=0)
        bad_json = json.dumps({"index": 99, "reasoning": "bad"})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=_mock_http_response(bad_json))

        with patch.object(ki, "_load_httpx") as mock_load:
            mock_load.return_value = MagicMock(AsyncClient=MagicMock(return_value=mock_client))
            idx, reason = await ki.enhance_decision(_ctx(), ["only_one"])

        assert idx == 0
        assert "heuristic" in reason


# ---------------------------------------------------------------------------
# _parse_response unit tests
# ---------------------------------------------------------------------------

class TestParseResponse:
    def test_valid_json(self):
        idx, r = KimiK25Integration._parse_response('{"index": 2, "reasoning": "best"}', 3)
        assert idx == 2
        assert r == "best"

    def test_markdown_fences_stripped(self):
        text = "```json\n{\"index\": 1, \"reasoning\": \"ok\"}\n```"
        idx, _ = KimiK25Integration._parse_response(text, 2)
        assert idx == 1

    def test_no_json_raises(self):
        with pytest.raises(ValueError):
            KimiK25Integration._parse_response("no JSON here", 3)

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            KimiK25Integration._parse_response('{"index": 5, "reasoning": "x"}', 3)

    def test_negative_index_raises(self):
        with pytest.raises(ValueError):
            KimiK25Integration._parse_response('{"index": -1, "reasoning": "x"}', 3)


# ---------------------------------------------------------------------------
# _heuristic_fallback scoring
# ---------------------------------------------------------------------------

class TestHeuristicFallback:
    def test_prefers_safe_option(self):
        ctx = _ctx()
        idx, reason = KimiK25Integration._heuristic_fallback(ctx, ["risky", "safe-path"])
        assert idx == 1  # "safe" keyword scores higher

    def test_fallback_reason_contains_heuristic(self):
        ctx = _ctx()
        _, reason = KimiK25Integration._heuristic_fallback(ctx, ["a", "b"])
        assert "heuristic" in reason

    def test_healing_type_boosts_score(self):
        ctx = _ctx(decision_type=DecisionType.HEALING)
        # All options equal — healing boost applies uniformly; first gets tie-breaker
        idx, _ = KimiK25Integration._heuristic_fallback(ctx, ["x", "y"])
        assert idx == 0  # tie → first (tie-breaker)

    def test_single_option_returns_zero(self):
        ctx = _ctx()
        idx, _ = KimiK25Integration._heuristic_fallback(ctx, ["only"])
        assert idx == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_initial_stats(self):
        ki = _integration()
        stats = ki.get_stats()
        assert stats["request_count"] == 0
        assert stats["error_count"] == 0
        assert stats["avg_latency_ms"] == 0.0
        assert stats["enabled"] is True

    def test_model_and_endpoint_in_stats(self):
        ki = _integration()
        stats = ki.get_stats()
        assert "model" in stats
        assert "endpoint" in stats
