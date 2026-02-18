"""Alias tests for brief_generator module — see test_ai_navigation_unit.py for full suite."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.ai.navigation.brief_generator import BriefGenerator


class TestBriefGeneratorModule:
    def test_import(self):
        assert BriefGenerator is not None

    def test_instantiate(self):
        bg = BriefGenerator()
        assert hasattr(bg, "generate_markdown")

    def test_generate_markdown_returns_string(self):
        bg = BriefGenerator()
        result = bg.generate_markdown(
            [{"title": "Test", "summary": "Summary", "url": "http://t.co",
              "relevance_score": 0.9, "source": "test", "category": "security"}],
            actions=["monitor PQC standards"],
        )
        assert isinstance(result, str)
