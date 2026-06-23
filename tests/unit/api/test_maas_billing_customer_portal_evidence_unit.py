import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
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


def test_create_customer_portal_publishes_redacted_portal_event(
    monkeypatch,
    tmp_path,
):
    db = _db_session()
    try:
        user_id = "portal-user-secret"
        stripe_customer_id = "cus_portal_secret"
        portal_session_id = "bps_portal_secret"
        portal_url = "https://billing.stripe.test/session/secret"
        user = User(
            id=user_id,
            email="portal-evidence@test.local",
            full_name="Secret Portal User",
            password_hash="test-hash",
            api_key="portal-evidence-key",
            role="user",
            plan="pro",
            stripe_customer_id=stripe_customer_id,
        )
        db.add(user)
        db.commit()

        async def _execute_stripe_call(_operation, **_kwargs):
            return SimpleNamespace(id=portal_session_id, url=portal_url)

        monkeypatch.setattr(billing_mod, "STRIPE_SECRET_KEY", "sk_test_portal")
        monkeypatch.setattr(billing_mod, "_execute_stripe_call", _execute_stripe_call)

        bus = EventBus(str(tmp_path))
        response = asyncio.run(
            billing_mod.create_customer_portal(
                _DummyRequest(bus),
                current_user=user,
                db=db,
            )
        )

        assert response["url"] == portal_url
        assert response["claim_gate"]["checkout_intent_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["customer_dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "maas_billing.customer_portal"
        assert response["cross_plane_claim_gate"]["allowed"] is False
        assert "does not prove subscription changes" in response["claim_boundary"]

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-customer-portal",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["component"] == "api.maas_billing"
        assert payload["operation"] == "create_customer_portal"
        assert payload["stage"] == "portal_session_created"
        assert payload["status"] == "success"
        assert payload["service_name"] == "maas-billing"
        assert payload["source_alias"] == "maas-billing-customer-portal"
        assert payload["layer"] == "billing_customer_portal_intent"
        assert payload["provider"] == "stripe"
        assert payload["stripe_configured"] is True
        assert payload["portal_url_present"] is True
        assert payload["local_db_write"] is False
        assert len(payload["user_id_hash"]) == 16
        assert len(payload["stripe_customer_id_hash"]) == 16
        assert len(payload["stripe_portal_session_id_hash"]) == 16
        assert payload["raw_identifiers_redacted"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert user.email not in serialized_payload
        assert user.full_name not in serialized_payload
        assert stripe_customer_id not in serialized_payload
        assert portal_session_id not in serialized_payload
        assert portal_url not in serialized_payload
    finally:
        db.close()


def test_create_customer_portal_missing_customer_publishes_redacted_event(tmp_path):
    db = _db_session()
    try:
        user_id = "portal-missing-user-secret"
        user = User(
            id=user_id,
            email="portal-missing@test.local",
            password_hash="test-hash",
            api_key="portal-missing-key",
            role="user",
            plan="free",
        )
        db.add(user)
        db.commit()

        bus = EventBus(str(tmp_path))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                billing_mod.create_customer_portal(
                    _DummyRequest(bus),
                    current_user=user,
                    db=db,
                )
            )

        assert exc_info.value.status_code == 400
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-customer-portal",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["stage"] == "customer_missing"
        assert payload["status"] == "failed"
        assert payload["portal_url_present"] is False
        assert payload["raw_identifiers_redacted"] is True
        assert user_id not in json.dumps(payload, sort_keys=True)
    finally:
        db.close()
