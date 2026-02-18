"""Alias tests for deep_search module — see test_ai_navigation_unit.py for full suite."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.ai.navigation.deep_search import DeepSearcher


class TestDeepSearchModule:
    def test_import(self):
        assert DeepSearcher is not None

    def test_instantiate(self):
        ds = DeepSearcher()
        assert hasattr(ds, "perform_search")

    @pytest.mark.asyncio
    async def test_perform_search_returns_list(self):
        ds = DeepSearcher()
        result = await ds.perform_search("post-quantum cryptography")
        assert isinstance(result, list)
