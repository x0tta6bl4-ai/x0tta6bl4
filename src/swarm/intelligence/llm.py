"""
Kimi K2.5 (or OpenAI-compatible) LLM integration for Swarm decisions.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .types import DecisionContext, DecisionType

logger = logging.getLogger(__name__)

class KimiK25Integration:
    """
    Integration with Kimi K2.5 (or any OpenAI-compatible) LLM for swarm decisions.

    Calls the chat-completions endpoint to get a recommendation from ``options``
    given a ``DecisionContext``.  Falls back to a score-based heuristic when the
    endpoint is unreachable, returns an unparseable response, or times out.

    Configuration
    -------------
    - ``api_endpoint``: full URL, e.g. ``https://api.moonshot.cn/v1`` or a
      local proxy.  The path ``/chat/completions`` is appended automatically.
    - ``api_key``: Bearer token; can also be supplied via ``KIMI_API_KEY`` env
      var.
    - ``model``: model tag; defaults to ``moonshot-v1-8k``.
    - ``timeout_s``: HTTP timeout in seconds (default 30).
    - ``max_retries``: number of retry attempts on transient errors (default 2).
    """

    _DEFAULT_ENDPOINT = "https://api.moonshot.cn/v1"
    _MODEL = "moonshot-v1-8k"
    _SYSTEM_PROMPT = (
        "You are a distributed-systems decision-making assistant for an autonomous "
        "mesh node. Given a decision context and a numbered list of options, reply "
        "with ONLY a JSON object: {\"index\": <0-based int>, \"reasoning\": <string>}. "
        "Choose the option that best balances safety, performance, and fault tolerance."
    )

    def __init__(
        self,
        enabled: bool = False,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: float = 30.0,
        max_retries: int = 2,
    ):
        self.enabled = enabled
        self.api_endpoint = (api_endpoint or self._DEFAULT_ENDPOINT).rstrip("/")
        self._api_key = api_key or ""
        self._model = model or self._MODEL
        self._timeout_s = timeout_s
        self._max_retries = max_retries

        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

        # Lazy-imported to avoid hard dep at module level
        self._httpx: Optional[Any] = None

    def _get_api_key(self) -> str:
        import os
        return self._api_key or os.environ.get("KIMI_API_KEY", "")

    def _load_httpx(self) -> Any:
        if self._httpx is None:
            import httpx  # already in requirements.txt
            self._httpx = httpx
        return self._httpx

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_user_message(self, context: DecisionContext, options: List[Any]) -> str:
        import json as _json
        lines = [
            f"Decision topic: {context.topic}",
            f"Type: {context.decision_type.value}",
            f"Priority: {context.priority.value}",
        ]
        if context.description:
            lines.append(f"Description: {context.description}")
        if context.data:
            lines.append(f"Context data: {_json.dumps(context.data, default=str)}")
        lines.append(f"\nOptions ({len(options)} total):")
        for i, opt in enumerate(options):
            lines.append(f"  [{i}] {opt}")
        lines.append("\nRespond with JSON only: {\"index\": <int>, \"reasoning\": <str>}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(text: str, n_options: int) -> Tuple[int, str]:
        """Extract index+reasoning from LLM JSON reply; raise ValueError on failure."""
        import json as _json
        import re

        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
        # Find first {...} block
        match = re.search(r"\{[^{}]+\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in: {text!r}")
        obj = _json.loads(match.group())
        idx = int(obj["index"])
        if not (0 <= idx < n_options):
            raise ValueError(f"index {idx} out of range [0, {n_options})")
        reasoning = str(obj.get("reasoning", ""))
        return idx, reasoning

    # ------------------------------------------------------------------
    # Score-based fallback (no LLM call)
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_fallback(context: DecisionContext, options: List[Any]) -> Tuple[int, str]:
        """
        Simple local heuristic used when LLM is unavailable.

        Scoring rules (higher = better):
        - HEALING / FAULT_TOLERANCE options score +2
        - Options whose string repr contains "safe", "stable", "primary" score +1
        - First option gets +0.5 tie-breaker
        Returns the highest-scoring option index.
        """
        priority_keywords = {"safe", "stable", "primary", "main", "default"}
        high_priority_types = {DecisionType.HEALING, DecisionType.FAULT_TOLERANCE}
        scores = []
        for i, opt in enumerate(options):
            score = 0.0
            opt_str = str(opt).lower()
            if context.decision_type in high_priority_types:
                score += 2.0
            if any(kw in opt_str for kw in priority_keywords):
                score += 1.0
            if i == 0:
                score += 0.5  # tie-breaker
            scores.append(score)
        best = max(range(len(scores)), key=lambda i: scores[i])
        return best, f"heuristic fallback (LLM unavailable): selected option {best}"

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def enhance_decision(
        self,
        context: DecisionContext,
        options: List[Any],
    ) -> Tuple[int, str]:
        """
        Use Kimi K2.5 LLM to recommend the best option.

        Returns ``(recommended_option_index, reasoning_string)``.
        Falls back to a local heuristic on any error or timeout.
        """
        if not self.enabled or not options:
            return (0, "LLM not enabled")

        start_time = time.time()

        # Resolve key; if missing, skip the real call entirely
        api_key = self._get_api_key()
        if not api_key:
            logger.debug("KimiK25Integration: no API key — using heuristic fallback")
            return self._heuristic_fallback(context, options)

        httpx = self._load_httpx()
        url = f"{self.api_endpoint}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_message(context, options)},
            ],
            "temperature": 0.2,
            "max_tokens": 256,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                idx, reasoning = self._parse_response(content, len(options))

                elapsed_ms = (time.time() - start_time) * 1000
                self._request_count += 1
                self._total_latency_ms += elapsed_ms
                logger.debug(
                    "KimiK25Integration: option=%d latency=%.0fms attempt=%d",
                    idx, elapsed_ms, attempt,
                )
                return idx, reasoning

            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # back-off

        self._error_count += 1
        logger.warning("KimiK25Integration: all attempts failed (%s) — heuristic fallback", last_exc)
        return self._heuristic_fallback(context, options)

    def get_stats(self) -> Dict[str, Any]:
        """Return runtime statistics for monitoring."""
        return {
            "enabled": self.enabled,
            "model": self._model,
            "endpoint": self.api_endpoint,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0 else 0.0
            ),
        }
