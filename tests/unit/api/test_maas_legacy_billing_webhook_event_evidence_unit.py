import asyncio
import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, User


class _DummyRequest:
    def __init__(self, payload: bytes, event_bus: EventBus):
        self._payload = payload
        self.state = SimpleNamespace(event_bus=event_bus)

    async def body(self) -> bytes:
        return self._payload


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_legacy_billing_webhook_publishes_redacted_eventbus_evidence(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv("X0T_BILLING_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", raising=False)

    user = User(
        id=f"usr-{uuid.uuid4().hex[:8]}",
        email=f"legacy-billing-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="test-hash",
        api_key=f"key-{uuid.uuid4().hex}",
        role="user",
        plan="starter",
    )
    db_session.add(user)
    db_session.commit()

    raw_event_id = f"evt_legacy_{uuid.uuid4().hex}"
    raw_customer_id = f"cus_{uuid.uuid4().hex}"
    raw_subscription_id = f"sub_{uuid.uuid4().hex}"
    payload = {
        "event_id": raw_event_id,
        "event_type": "plan.upgraded",
        "plan": "pro",
        "user_id": user.id,
        "email": user.email,
        "customer_id": raw_customer_id,
        "subscription_id": raw_subscription_id,
    }
    raw_payload = json.dumps(payload).encode("utf-8")
    bus = EventBus(str(tmp_path))

    result = asyncio.run(
        legacy_mod.legacy_billing_webhook(
            legacy_mod.BillingWebhookRequest(**payload),
            _DummyRequest(raw_payload, bus),
            db_session,
        )
    )

    assert result["processed"] is True
    assert result["plan_before"] == "starter"
    assert result["plan_after"] == "pro"

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="maas-legacy-billing",
    )
    assert len(events) == 1
    event_payload = events[0].data
    assert event_payload["component"] == "api.maas_legacy"
    assert event_payload["operation"] == "billing_webhook"
    assert event_payload["stage"] == "processed"
    assert event_payload["status"] == "success"
    assert event_payload["plan_before"] == "starter"
    assert event_payload["plan_after"] == "pro"
    assert event_payload["billing_event_id_hash"]
    assert event_payload["customer_id_hash"]
    assert event_payload["subscription_id_hash"]
    assert event_payload["email_hash"]
    assert event_payload["raw_identifiers_redacted"] is True

    serialized_event_payload = json.dumps(event_payload, sort_keys=True)
    assert raw_event_id not in serialized_event_payload
    assert raw_customer_id not in serialized_event_payload
    assert raw_subscription_id not in serialized_event_payload
    assert user.email not in serialized_event_payload

    replay_result = asyncio.run(
        legacy_mod.legacy_billing_webhook(
            legacy_mod.BillingWebhookRequest(**payload),
            _DummyRequest(raw_payload, bus),
            db_session,
        )
    )

    assert replay_result["idempotent_replay"] is True
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="maas-legacy-billing",
    )
    assert len(events) == 2
    replay_payload = events[-1].data
    assert replay_payload["component"] == "api.maas_legacy"
    assert replay_payload["stage"] == "idempotent_replay"
    assert replay_payload["status"] == "replayed"
    assert replay_payload["idempotent_replay"] is True

    serialized_replay_payload = json.dumps(replay_payload, sort_keys=True)
    assert raw_event_id not in serialized_replay_payload
    assert raw_customer_id not in serialized_replay_payload
    assert raw_subscription_id not in serialized_replay_payload
    assert user.email not in serialized_replay_payload
