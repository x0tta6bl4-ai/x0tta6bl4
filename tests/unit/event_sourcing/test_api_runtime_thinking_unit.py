"""Runtime-thinking checks for Event Sourcing API endpoints."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.event_sourcing.command_bus import CommandResult
from src.event_sourcing.query_bus import QueryResult
from src.event_sourcing import api


def _assert_event_api_thinking(status, operation):
    techniques = set(status["techniques"])
    assert status["profile"]["role"] == "coordination"
    assert "mape_k" in techniques
    assert "mind_maps" in techniques
    assert "causal_analysis" in techniques
    assert "graphsage" in techniques
    assert "zero_trust_review" in techniques
    assert "reverse_planning" in techniques
    context = status["last_context"]
    assert context["applied"]["framing"]["problem"] == (
        "event_sourcing_api_operation"
    )
    constraints = context["applied"]["framing"]["constraints"]
    assert constraints["operation"] == operation
    assert constraints["raw_command_payload_redacted"] is True
    assert constraints["raw_query_parameters_redacted"] is True
    assert constraints["raw_event_payloads_redacted"] is True
    assert constraints["raw_errors_redacted"] is True
    assert constraints["local_api_result_is_not_external_delivery_proof"] is True


@pytest.mark.asyncio
async def test_execute_command_thinking_redacts_payload_and_type(monkeypatch):
    bus = SimpleNamespace(
        execute=lambda command: CommandResult(
            success=True,
            result={"ok": True},
            events_produced=1,
        )
    )
    monkeypatch.setattr(api, "get_command_bus", lambda: bus)

    response = await api.execute_command(
        api.CommandRequest(
            command_type="SECRET_COMMAND_TYPE",
            payload={"field": "SECRET_COMMAND_PAYLOAD"},
            metadata={"trace": "SECRET_COMMAND_METADATA"},
        ),
        None,
    )

    assert response.success is True
    status = api.get_api_thinking_status()
    _assert_event_api_thinking(status, "execute_command")
    constraints = status["last_context"]["applied"]["framing"]["constraints"]
    assert constraints["success"] is True
    assert constraints["events_produced"] == 1
    rendered = str(status)
    assert "SECRET_COMMAND_TYPE" not in rendered
    assert "SECRET_COMMAND_PAYLOAD" not in rendered
    assert "SECRET_COMMAND_METADATA" not in rendered


@pytest.mark.asyncio
async def test_execute_query_thinking_redacts_parameters(monkeypatch):
    bus = SimpleNamespace(
        execute=lambda query: QueryResult(
            success=True,
            result={"ok": True},
            from_cache=True,
        )
    )
    monkeypatch.setattr(api, "get_query_bus", lambda: bus)

    response = await api.execute_query(
        api.QueryRequest(
            query_type="SECRET_QUERY_TYPE",
            parameters={"user": "SECRET_QUERY_PARAMETER"},
            options={"scope": "SECRET_QUERY_OPTION"},
        ),
        None,
    )

    assert response.from_cache is True
    status = api.get_api_thinking_status()
    _assert_event_api_thinking(status, "execute_query")
    constraints = status["last_context"]["applied"]["framing"]["constraints"]
    assert constraints["from_cache"] is True
    rendered = str(status)
    assert "SECRET_QUERY_TYPE" not in rendered
    assert "SECRET_QUERY_PARAMETER" not in rendered
    assert "SECRET_QUERY_OPTION" not in rendered


@pytest.mark.asyncio
async def test_execute_command_failure_thinking_redacts_error(monkeypatch):
    def _raise(_command):
        raise RuntimeError("SECRET_COMMAND_ERROR_DETAIL")

    monkeypatch.setattr(api, "get_command_bus", lambda: SimpleNamespace(execute=_raise))

    with pytest.raises(HTTPException) as exc_info:
        await api.execute_command(
            api.CommandRequest(command_type="SECRET_FAIL_COMMAND", payload={}),
            None,
        )

    assert exc_info.value.status_code == 400
    status = api.get_api_thinking_status()
    _assert_event_api_thinking(status, "execute_command")
    constraints = status["last_context"]["applied"]["framing"]["constraints"]
    assert constraints["error_type"] == "RuntimeError"
    rendered = str(status)
    assert "SECRET_FAIL_COMMAND" not in rendered
    assert "SECRET_COMMAND_ERROR_DETAIL" not in rendered
