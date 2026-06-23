from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

from src.api import maas_governance as gov
from src.coordination.events import EventBus, EventType


def _request_with_bus(bus: EventBus) -> SimpleNamespace:
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def test_governance_proposal_event_redacts_raw_identity_and_payload(tmp_path):
    bus = EventBus(str(tmp_path))
    request = _request_with_bus(bus)
    user = SimpleNamespace(
        id="user-raw-123",
        email="owner@example.com",
        plan="pro",
        role="admin",
    )
    proposal_request = gov.ProposalCreate(
        title="Sensitive global parameter change",
        description="This proposal body should never be copied into events.",
        duration_hours=12,
        actions=[
            gov.GovernanceAction(
                type="update_config",
                params={"key": "global_price_multiplier", "value": "do-not-copy"},
            )
        ],
    )
    proposal = SimpleNamespace(
        id="prop-raw-123",
        title=proposal_request.title,
        description=proposal_request.description,
        state="active",
        actions_json=json.dumps([action.dict() for action in proposal_request.actions]),
        votes=[],
        execution_hash=None,
        executed_at=None,
    )

    event_id = gov._publish_governance_proposal_event(
        request,
        source_agent=gov._PROPOSAL_CREATE_SOURCE_AGENT,
        layer=gov._PROPOSAL_CREATE_LAYER,
        stage="proposal_create_control",
        operation="maas_governance_proposal_create",
        status="created",
        current_user=user,
        proposal_id=proposal.id,
        proposal=proposal,
        proposal_request=proposal_request,
        db_backed=True,
        audit_log_attempted=True,
        http_status_code=200,
        duration_ms=12.3456,
    )

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=gov._PROPOSAL_CREATE_SOURCE_AGENT,
        limit=10,
    )
    payload = events[-1].data
    payload_text = str(payload)

    assert event_id == events[-1].event_id
    assert payload["proposal_id_hash"]
    assert payload["actor_user_id_hash"]
    assert payload["actor_email_hash"]
    assert payload["action_counts"]["update_config"] == 1
    assert payload["duration_ms"] == 12.346
    assert payload["http_status_code"] == 200
    assert payload["service_identity"]["redacted"] is True
    assert payload["raw_identifiers_redacted"] is True
    assert payload["raw_payload_redacted"] is True
    assert "prop-raw-123" not in payload_text
    assert "user-raw-123" not in payload_text
    assert "owner@example.com" not in payload_text
    assert "Sensitive global parameter change" not in payload_text
    assert "do-not-copy" not in payload_text


def test_list_proposals_endpoint_publishes_observed_state_event(tmp_path):
    bus = EventBus(str(tmp_path))
    request = _request_with_bus(bus)
    proposal = SimpleNamespace(
        id="prop-list-raw",
        title="Visible only in API response",
        description="The event must not copy this description.",
        state="active",
        actions_json=json.dumps([{"type": "rotate_keys", "params": {}}]),
        votes=[],
        end_time=datetime.utcnow() + timedelta(hours=1),
    )

    class Query:
        def order_by(self, *_args):
            return self

        def all(self):
            return [proposal]

    class DB:
        def query(self, *_args):
            return Query()

        def add(self, *_args):
            return None

        def commit(self):
            return None

    response = asyncio.run(gov.list_proposals(db=DB(), request=request))
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent=gov._PROPOSAL_LIST_SOURCE_AGENT,
        limit=10,
    )
    payload = events[-1].data
    payload_text = str(payload)

    assert response["proposals"][0]["id"] == "prop-list-raw"
    assert payload["observed_state"] is True
    assert payload["read_only"] is True
    assert payload["proposal_count"] == 1
    assert payload["proposal_state_counts"]["active"] == 1
    assert payload["proposal_id_hashes"]
    assert "prop-list-raw" not in payload_text
    assert "Visible only in API response" not in payload_text
    assert "The event must not copy this description." not in payload_text
