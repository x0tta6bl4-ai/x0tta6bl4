import asyncio
import json
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_billing as billing_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, User


class _DummyRequest:
    def __init__(self, event_bus: EventBus):
        self.state = SimpleNamespace(event_bus=event_bus)


def _db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_create_subscription_session_publishes_redacted_checkout_event(
    monkeypatch,
    tmp_path,
):
    db = _db_session()
    try:
        user_id = "subscription-checkout-user-secret"
        stripe_customer_id = "cus_subscription_checkout_secret"
        stripe_session_id = "cs_subscription_checkout_secret"
        price_id = "price_subscription_checkout_secret"
        checkout_url = "https://checkout.stripe.test/subscription/secret"
        user = User(
            id=user_id,
            email="subscription-checkout@test.local",
            full_name="Secret Subscription Checkout User",
            password_hash="test-hash",
            api_key="subscription-checkout-key",
            role="user",
            plan="starter",
        )
        db.add(user)
        db.commit()

        stripe_responses = [
            SimpleNamespace(id=stripe_customer_id),
            SimpleNamespace(id=stripe_session_id, url=checkout_url),
        ]

        async def _execute_stripe_call(_operation, **_kwargs):
            return stripe_responses.pop(0)

        monkeypatch.setattr(billing_mod, "STRIPE_SECRET_KEY", "sk_test_subscription")
        monkeypatch.setattr(
            billing_mod,
            "STRIPE_PLANS",
            {"starter": "price_starter", "pro": price_id, "enterprise": "price_ent"},
        )
        monkeypatch.setattr(billing_mod, "_execute_stripe_call", _execute_stripe_call)
        monkeypatch.setattr(billing_mod, "record_audit_log", lambda *args, **kwargs: None)

        bus = EventBus(str(tmp_path))
        response = asyncio.run(
            billing_mod.create_subscription_session(
                "pro",
                _DummyRequest(bus),
                current_user=user,
                db=db,
            )
        )

        assert response["url"] == checkout_url
        assert response["claim_gate"]["checkout_intent_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["customer_dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "maas_billing.subscription_checkout"
        assert response["cross_plane_claim_gate"]["allowed"] is False
        assert "does not prove customer payment" in response["claim_boundary"]
        assert user.stripe_customer_id == stripe_customer_id

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-subscription-checkout",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["component"] == "api.maas_billing"
        assert payload["operation"] == "create_subscription_session"
        assert payload["stage"] == "subscription_checkout_created"
        assert payload["status"] == "success"
        assert payload["service_name"] == "maas-billing"
        assert payload["source_alias"] == "maas-billing-subscription-checkout"
        assert payload["layer"] == "billing_subscription_checkout_intent"
        assert payload["provider"] == "stripe"
        assert payload["plan"] == "pro"
        assert payload["stripe_configured"] is True
        assert payload["customer_created"] is True
        assert payload["checkout_url_present"] is True
        assert payload["local_db_write"] is True
        assert payload["audit_recorded"] is True
        assert len(payload["user_id_hash"]) == 16
        assert len(payload["stripe_customer_id_hash"]) == 16
        assert len(payload["stripe_session_id_hash"]) == 16
        assert len(payload["price_id_hash"]) == 16
        assert payload["raw_identifiers_redacted"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert user.email not in serialized_payload
        assert user.full_name not in serialized_payload
        assert stripe_customer_id not in serialized_payload
        assert stripe_session_id not in serialized_payload
        assert price_id not in serialized_payload
        assert checkout_url not in serialized_payload
    finally:
        db.close()
