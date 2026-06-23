import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_billing as billing_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, Invoice, User
from src.services.service_event_trace import event_trace_evidence_summary


class _DummyRequest:
    def __init__(self, event_bus: EventBus):
        self.state = SimpleNamespace(event_bus=event_bus)


def _db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_create_checkout_session_publishes_redacted_checkout_event(
    monkeypatch,
    tmp_path,
):
    db = _db_session()
    try:
        user_id = "checkout-user-secret"
        mesh_id = "checkout-mesh-secret"
        invoice_id = "checkout-invoice-secret"
        stripe_session_id = "cs_checkout_secret"
        checkout_url = "https://checkout.stripe.test/session/secret"
        user = User(
            id=user_id,
            email="checkout-evidence@test.local",
            password_hash="test-hash",
            api_key="checkout-evidence-key",
            role="user",
            plan="starter",
        )
        invoice = Invoice(
            id=invoice_id,
            user_id=user_id,
            mesh_id=mesh_id,
            total_amount=5000,
            currency="USD",
            status="issued",
            period_start=datetime(2026, 5, 29, 0, 0, 0),
            period_end=datetime(2026, 5, 29, 1, 0, 0),
        )
        db.add(user)
        db.add(invoice)
        db.commit()

        async def _call_with_reliability(operation, **_kwargs):
            return await operation()

        monkeypatch.setattr(billing_mod, "STRIPE_SECRET_KEY", "sk_test_checkout")
        monkeypatch.setattr(
            billing_mod,
            "call_with_reliability",
            _call_with_reliability,
        )
        monkeypatch.setattr(
            billing_mod.stripe.checkout.Session,
            "create",
            lambda **_kwargs: SimpleNamespace(
                id=stripe_session_id,
                url=checkout_url,
            ),
        )

        bus = EventBus(str(tmp_path))
        response = asyncio.run(
            billing_mod.create_checkout_session(
                invoice_id,
                _DummyRequest(bus),
                current_user=user,
                db=db,
            )
        )

        stored_invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        assert response["url"] == checkout_url
        assert response["claim_gate"]["checkout_intent_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["customer_dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "maas_billing.invoice_checkout"
        assert response["cross_plane_claim_gate"]["allowed"] is False
        assert "does not prove customer payment" in response["claim_boundary"]
        assert stored_invoice.stripe_session_id == stripe_session_id

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-checkout",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["component"] == "api.maas_billing"
        assert payload["operation"] == "create_checkout_session"
        assert payload["stage"] == "checkout_session_created"
        assert payload["status"] == "success"
        assert payload["service_name"] == "maas-billing"
        assert payload["source_alias"] == "maas-billing-checkout"
        assert payload["layer"] == "billing_checkout_intent"
        assert payload["provider"] == "stripe"
        assert payload["stripe_configured"] is True
        assert payload["checkout_url_present"] is True
        assert payload["local_db_write"] is True
        assert payload["amount_total"] == 5000
        assert payload["currency"] == "USD"
        assert payload["raw_identifiers_redacted"] is True
        assert payload["settlement_evidence"]["source_quality"] == "stripe_checkout_intent_created"
        assert payload["settlement_evidence"]["settlement_action"] == "checkout_session_intent_only"
        assert payload["settlement_evidence"]["dataplane_confirmed"] is False
        assert payload["settlement_evidence"]["live_provider_settlement_confirmed"] is False
        assert payload["settlement_evidence"]["bank_settlement_confirmed"] is False
        assert payload["settlement_evidence"]["chain_finality_confirmed"] is False
        assert payload["settlement_evidence"]["db_write_evidence"]["committed"] is True
        assert payload["settlement_evidence"]["output_summary"]["stripe_session_present"] is True

        trace_summary = event_trace_evidence_summary(payload)
        settlement_summary = trace_summary["settlement_evidence"]
        assert settlement_summary["present"] is True
        assert settlement_summary["provider"] == "stripe"
        assert settlement_summary["dataplane_confirmed"] is False
        assert settlement_summary["live_provider_settlement_confirmed"] is False
        assert settlement_summary["bank_settlement_confirmed"] is False
        assert settlement_summary["chain_finality_confirmed"] is False
        assert settlement_summary["db_write_evidence"]["committed"] is True
        assert settlement_summary["output_summary"]["stripe_session_present"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert mesh_id not in serialized_payload
        assert invoice_id not in serialized_payload
        assert stripe_session_id not in serialized_payload
        assert checkout_url not in serialized_payload
    finally:
        db.close()


def test_paid_invoice_checkout_response_keeps_payment_claims_blocked(tmp_path):
    db = _db_session()
    try:
        user_id = "paid-checkout-user-secret"
        mesh_id = "paid-checkout-mesh-secret"
        invoice_id = "paid-checkout-invoice-secret"
        user = User(
            id=user_id,
            email="paid-checkout-evidence@test.local",
            password_hash="test-hash",
            api_key="paid-checkout-evidence-key",
            role="user",
            plan="starter",
        )
        invoice = Invoice(
            id=invoice_id,
            user_id=user_id,
            mesh_id=mesh_id,
            total_amount=5000,
            currency="USD",
            status="paid",
            period_start=datetime(2026, 5, 29, 0, 0, 0),
            period_end=datetime(2026, 5, 29, 1, 0, 0),
        )
        db.add(user)
        db.add(invoice)
        db.commit()

        bus = EventBus(str(tmp_path))
        response = asyncio.run(
            billing_mod.create_checkout_session(
                invoice_id,
                _DummyRequest(bus),
                current_user=user,
                db=db,
            )
        )

        assert response["message"] == "Invoice already paid"
        assert response["url"] is None
        assert response["claim_gate"]["stripe_status_observation_claim_allowed"] is True
        assert response["claim_gate"]["payment_provider_settlement_claim_allowed"] is False
        assert response["claim_gate"]["bank_settlement_claim_allowed"] is False
        assert response["claim_gate"]["customer_dataplane_delivery_claim_allowed"] is False
        assert response["claim_gate"]["production_readiness_claim_allowed"] is False
        assert response["cross_plane_claim_gate"]["surface"] == "maas_billing.invoice_checkout"
        assert response["cross_plane_claim_gate"]["allowed"] is False
    finally:
        db.close()
