import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_billing as billing_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, User


class _DummyRequest:
    def __init__(self, event_bus: EventBus):
        self._payload = b"{}"
        self.headers = {"stripe-signature": "sig"}
        self.state = SimpleNamespace(event_bus=event_bus)
        self.method = "POST"
        self.url = SimpleNamespace(path="/api/v1/maas/billing/webhook/stripe")
        self.client = SimpleNamespace(host="127.0.0.1")

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


def _create_user(db_session, *, customer_id: str, subscription_id: str) -> User:
    user = User(
        id="subscription-webhook-user-secret",
        email="subscription-webhook@test.local",
        password_hash="test-hash",
        api_key="subscription-webhook-key",
        role="user",
        plan="pro",
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.mark.asyncio
async def test_subscription_updated_webhook_publishes_redacted_lifecycle_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    customer_id = "cus_subscription_webhook_update_secret"
    subscription_id = "sub_subscription_webhook_update_secret"
    stripe_event_id = "evt_subscription_webhook_update_secret"
    user = _create_user(
        db_session,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    bus = EventBus(str(tmp_path))
    monkeypatch.setattr(billing_mod, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing_mod, "record_audit_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        billing_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: {
            "id": stripe_event_id,
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": subscription_id,
                    "customer": customer_id,
                    "status": "active",
                }
            },
        },
    )

    result = await billing_mod.stripe_webhook(_DummyRequest(bus), db_session)

    assert result == {"status": "success"}
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="maas-billing-subscription-webhook",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["component"] == "api.maas_billing"
    assert payload["operation"] == "stripe_subscription_webhook"
    assert payload["stage"] == "subscription_updated"
    assert payload["status"] == "success"
    assert payload["service_name"] == "maas-billing"
    assert payload["source_alias"] == "maas-billing-subscription-webhook"
    assert payload["layer"] == "billing_subscription_webhook_lifecycle"
    assert payload["stripe_event_type"] == "customer.subscription.updated"
    assert payload["subscription_status"] == "active"
    assert payload["plan_before"] == "pro"
    assert payload["plan_after"] == "pro"
    assert payload["local_db_write"] is False
    assert payload["audit_recorded"] is True
    assert len(payload["stripe_event_id_hash"]) == 16
    assert len(payload["stripe_customer_id_hash"]) == 16
    assert len(payload["stripe_subscription_id_hash"]) == 16
    assert len(payload["user_id_hash"]) == 16
    assert payload["raw_identifiers_redacted"] is True

    serialized_payload = json.dumps(payload, sort_keys=True)
    assert stripe_event_id not in serialized_payload
    assert customer_id not in serialized_payload
    assert subscription_id not in serialized_payload
    assert user.id not in serialized_payload
    assert user.email not in serialized_payload


@pytest.mark.asyncio
async def test_subscription_deleted_webhook_publishes_redacted_lifecycle_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    customer_id = "cus_subscription_webhook_delete_secret"
    subscription_id = "sub_subscription_webhook_delete_secret"
    stripe_event_id = "evt_subscription_webhook_delete_secret"
    user = _create_user(
        db_session,
        customer_id=customer_id,
        subscription_id=subscription_id,
    )
    bus = EventBus(str(tmp_path))
    monkeypatch.setattr(billing_mod, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing_mod, "record_audit_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        billing_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: {
            "id": stripe_event_id,
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": subscription_id,
                    "customer": customer_id,
                    "status": "canceled",
                }
            },
        },
    )

    result = await billing_mod.stripe_webhook(_DummyRequest(bus), db_session)

    assert result == {"status": "success"}
    assert user.plan == "free"
    assert user.stripe_subscription_id is None
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="maas-billing-subscription-webhook",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["stage"] == "subscription_cancelled"
    assert payload["status"] == "success"
    assert payload["stripe_event_type"] == "customer.subscription.deleted"
    assert payload["subscription_status"] == "canceled"
    assert payload["plan_before"] == "pro"
    assert payload["plan_after"] == "free"
    assert payload["local_db_write"] is True
    assert payload["audit_recorded"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized_payload = json.dumps(payload, sort_keys=True)
    assert stripe_event_id not in serialized_payload
    assert customer_id not in serialized_payload
    assert subscription_id not in serialized_payload
    assert user.id not in serialized_payload
    assert user.email not in serialized_payload
