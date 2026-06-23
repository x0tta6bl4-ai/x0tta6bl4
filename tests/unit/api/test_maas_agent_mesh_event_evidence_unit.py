from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api import maas_agent_mesh as mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


class _EvidenceBot:
    def __init__(self):
        self.config = SimpleNamespace(
            socks_host="127.0.0.1",
            socks_port=1080,
            health_urls=["https://private.example.invalid/health"],
            allow_external_urls=False,
            enable_execute=True,
        )
        self._history = []

    def run_once(self, *, auto_heal: bool, dry_run: bool):
        report = {
            "status": "degraded",
            "auto_heal": auto_heal,
            "dry_run": dry_run,
            "engine": "local-rule-engine",
            "external_ai_providers_used": False,
            "signals": [
                {
                    "name": "health_url:https://private.example.invalid/health",
                    "status": "fail",
                    "detail": "request error with private host",
                },
                {
                    "name": "proxy_delay_ms",
                    "status": "fail",
                    "detail": "latest delay=999ms",
                    "value": 999,
                },
            ],
            "proposed_actions": [
                {
                    "id": "restart_control_plane",
                    "reason": "local API health endpoint returned failures",
                }
            ],
            "executed_actions": [
                {
                    "id": "restart_control_plane",
                    "command": "/bin/echo private-command",
                    "attempted": auto_heal and not dry_run,
                    "success": False,
                    "detail": "private command output",
                }
            ],
        }
        self._history.append(report)
        return report

    def history(self, limit: int = 20):
        return self._history[-limit:][::-1]


def test_health_status_event_redacts_urls_commands_and_actor(monkeypatch, tmp_path):
    bus = EventBus(str(tmp_path))
    monkeypatch.setattr(mod, "_health_bot", _EvidenceBot())
    monkeypatch.setenv("MAAS_AGENT_BOT_TOKEN", "expected-token")
    user = {"id": "user-private", "email": "agent@example.com", "role": "admin"}

    response = asyncio.run(mod.health_status(_request(bus), _user=user))
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod._HEALTH_STATUS_SOURCE_AGENT,
        limit=10,
    )
    payload = events[-1].data
    payload_text = str(payload)

    assert response["status"] == "degraded"
    assert payload["report_status"] == "degraded"
    assert payload["signal_kind_counts"]["health_url"] == 1
    assert payload["signal_status_counts"]["fail"] == 2
    assert payload["raw_health_urls_redacted"] is True
    assert payload["raw_commands_redacted"] is True
    assert payload["raw_token_redacted"] is True
    assert "private.example.invalid" not in payload_text
    assert "/bin/echo private-command" not in payload_text
    assert "private command output" not in payload_text
    assert "user-private" not in payload_text
    assert "agent@example.com" not in payload_text
    assert "expected-token" not in payload_text


def test_health_run_denial_event_does_not_copy_agent_token(monkeypatch, tmp_path):
    bus = EventBus(str(tmp_path))
    monkeypatch.setattr(mod, "_health_bot", _EvidenceBot())
    monkeypatch.setenv("MAAS_AGENT_BOT_TOKEN", "expected-token")
    request = _request(bus)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            mod.run_health_bot(
                mod.HealthBotRunRequest(auto_heal=True, dry_run=False),
                x_agent_token="wrong-token",
                _user={"id": "user-private"},
                request=request,
            )
        )

    events = bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent=mod._HEALTH_RUN_SOURCE_AGENT,
        limit=10,
    )
    payload = events[-1].data
    payload_text = str(payload)

    assert exc_info.value.status_code == 403
    assert payload["status"] == "blocked"
    assert payload["control_action"] is True
    assert payload["token_header_present"] is True
    assert payload["exec_token_configured"] is True
    assert payload["reason"] == "exec_token_invalid"
    assert "wrong-token" not in payload_text
    assert "expected-token" not in payload_text
    assert "user-private" not in payload_text


def test_health_history_event_only_records_bounded_metadata(monkeypatch, tmp_path):
    bus = EventBus(str(tmp_path))
    bot = _EvidenceBot()
    bot.run_once(auto_heal=True, dry_run=True)
    monkeypatch.setattr(mod, "_health_bot", bot)

    response = asyncio.run(
        mod.health_history(limit=20, _user={"id": "user-private"}, request=_request(bus))
    )
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=mod._HEALTH_HISTORY_SOURCE_AGENT,
        limit=10,
    )
    payload = events[-1].data
    payload_text = str(payload)

    assert len(response["items"]) == 1
    assert payload["read_only"] is True
    assert payload["observed_state"] is True
    assert payload["history_item_count"] == 1
    assert payload["history_status_counts"]["degraded"] == 1
    assert "private.example.invalid" not in payload_text
    assert "/bin/echo private-command" not in payload_text
    assert "user-private" not in payload_text
