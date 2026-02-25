"""Unit tests for run_janitor.py entrypoint."""
import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestJanitorMain:
    def test_main_runs_janitor_loop(self):
        with patch("src.services.run_janitor.marketplace_janitor_loop", new_callable=AsyncMock) as mock_loop:
            with patch("asyncio.run") as mock_run:
                from src.services.run_janitor import main
                main()
                mock_run.assert_called_once()

    def test_main_handles_keyboard_interrupt(self):
        with patch("src.services.run_janitor.asyncio.run", side_effect=KeyboardInterrupt):
            from src.services.run_janitor import main
            # Should not raise
            main()

    def test_main_exits_on_fatal_error(self):
        with patch("src.services.run_janitor.asyncio.run", side_effect=RuntimeError("boom")):
            with patch("sys.exit") as mock_exit:
                from src.services.run_janitor import main
                main()
                mock_exit.assert_called_once_with(1)
