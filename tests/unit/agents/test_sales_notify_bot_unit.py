"""Unit tests for src.agents.sales_notify_bot."""

from __future__ import annotations

import asyncio
import json

import pytest

from src.agents import sales_notify_bot as mod


def test_check_business_state_sends_notification_on_first_offer(tmp_path, monkeypatch):
    state_file = tmp_path / "swarm_state.json"
    state_file.write_text(
        json.dumps({"business_stream": {"offer_ready": True}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STATE_FILE", str(state_file))

    bot = mod.SalesBot()
    sent = []
    monkeypatch.setattr(bot, "send_notification", lambda msg: sent.append(msg))

    bot.check_business_state()
    assert len(sent) == 1
    assert "COMMERCIAL OFFER IS READY" in sent[0]
    assert bot.last_offer_status is True

    # Second check with same state should not notify again.
    bot.check_business_state()
    assert len(sent) == 1


def test_check_business_state_handles_invalid_json(tmp_path, monkeypatch, caplog):
    state_file = tmp_path / "swarm_state.json"
    state_file.write_text("{invalid-json", encoding="utf-8")
    monkeypatch.setattr(mod, "STATE_FILE", str(state_file))

    bot = mod.SalesBot()
    bot.check_business_state()

    assert any("Error reading state" in msg for msg in caplog.messages)


def test_monitor_sales_log_smoke(tmp_path, monkeypatch):
    sales_log = tmp_path / "sales.log"
    sales_log.write_text("event1\nevent2\n", encoding="utf-8")
    monkeypatch.setattr(mod, "SALES_LOG", str(sales_log))

    bot = mod.SalesBot()
    bot.monitor_sales_log()  # no exception


def test_send_notification_prints_message(capsys):
    bot = mod.SalesBot()
    bot.send_notification("hello")
    out = capsys.readouterr().out
    assert "--> [TG] hello" in out


@pytest.mark.asyncio
async def test_run_calls_check_business_state(monkeypatch):
    bot = mod.SalesBot()
    called = {"count": 0}

    def _check():
        called["count"] += 1

    async def _cancel_sleep(_seconds):
        raise asyncio.CancelledError

    monkeypatch.setattr(bot, "check_business_state", _check)
    monkeypatch.setattr(mod.asyncio, "sleep", _cancel_sleep)

    with pytest.raises(asyncio.CancelledError):
        await bot.run()

    assert called["count"] == 1
