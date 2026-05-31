import uuid
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_billing as billing_mod
import src.api.maas_marketplace as marketplace_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, Invoice, User
from src.services.service_event_trace import event_trace_evidence_summary


class _DummyRequest:
    def __init__(
        self,
        payload: bytes = b"{}",
        signature: str = "sig",
        event_bus=None,
    ):
        self._payload = payload
        self.headers = {"stripe-signature": signature}
        self.state = SimpleNamespace(event_bus=event_bus) if event_bus else SimpleNamespace()
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


def _create_user(db_session) -> User:
    user = User(
        id=f"usr-{uuid.uuid4().hex[:8]}",
        email=f"billing-unit-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="test-hash",
        api_key=f"key-{uuid.uuid4().hex}",
        role="user",
        plan="free",
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.mark.asyncio
async def test_subscription_checkout_replay_is_idempotent(db_session, monkeypatch):
    user = _create_user(db_session)
    monkeypatch.setattr(billing_mod, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing_mod, "record_audit_log", lambda *args, **kwargs: None)

    fake_event = {
        "id": "evt_replay_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_sub_replay_1",
                "mode": "subscription",
                "payment_status": "paid",
                "subscription": "sub_replay_1",
                "currency": "usd",
                "amount_total": 4900,
                "metadata": {"user_id": user.id, "plan": "starter"},
            }
        },
    }
    monkeypatch.setattr(
        billing_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: fake_event,
    )

    request = _DummyRequest()
    first = await billing_mod.stripe_webhook(request, db_session)
    second = await billing_mod.stripe_webhook(request, db_session)

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert second.get("idempotent") is True

    invoices = db_session.query(Invoice).filter(Invoice.stripe_session_id == "cs_sub_replay_1").all()
    assert len(invoices) == 1
    assert invoices[0].status == "paid"


@pytest.mark.asyncio
async def test_subscription_bridge_mint_requires_explicit_flag(db_session, monkeypatch):
    user = _create_user(db_session)
    monkeypatch.setattr(billing_mod, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing_mod, "record_audit_log", lambda *args, **kwargs: None)

    class _FakeToken:
        def __init__(self):
            self.calls = []

        def mint(self, account, amount, reason):
            self.calls.append((account, amount, reason))

    class _FakeBridge:
        def __init__(self):
            self.mesh_token = _FakeToken()

    fake_bridge = _FakeBridge()
    monkeypatch.setattr(marketplace_mod, "_get_token_bridge", lambda: fake_bridge)

    event_without_flag = {
        "id": "evt_no_bridge",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_no_bridge",
                "mode": "subscription",
                "payment_status": "paid",
                "subscription": "sub_no_bridge",
                "currency": "usd",
                "amount_total": 1000,
                "metadata": {"user_id": user.id, "plan": "starter"},
            }
        },
    }
    monkeypatch.setattr(
        billing_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: event_without_flag,
    )
    await billing_mod.stripe_webhook(_DummyRequest(), db_session)
    assert fake_bridge.mesh_token.calls == []

    event_with_flag = {
        "id": "evt_with_bridge",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_with_bridge",
                "mode": "subscription",
                "payment_status": "paid",
                "subscription": "sub_with_bridge",
                "currency": "usd",
                "amount_total": 1200,
                "metadata": {"user_id": user.id, "plan": "starter", "bridge_x0t": "true"},
            }
        },
    }
    monkeypatch.setattr(
        billing_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: event_with_flag,
    )
    await billing_mod.stripe_webhook(_DummyRequest(), db_session)

    assert len(fake_bridge.mesh_token.calls) == 1
    account, amount, reason = fake_bridge.mesh_token.calls[0]
    assert account == user.id
    assert amount == 1200.0
    assert reason == "stripe_payment_cs_with_bridge"


@pytest.mark.asyncio
async def test_subscription_webhook_publishes_billing_event_trace(db_session, monkeypatch, tmp_path):
    user = _create_user(db_session)
    bus = EventBus(str(tmp_path))
    monkeypatch.setattr(billing_mod, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing_mod, "record_audit_log", lambda *args, **kwargs: None)

    class _FakeToken:
        def __init__(self):
            self.calls = []

        def mint(self, account, amount, reason):
            self.calls.append((account, amount, reason))

    class _FakeBridge:
        def __init__(self):
            self.mesh_token = _FakeToken()

    fake_bridge = _FakeBridge()
    monkeypatch.setattr(marketplace_mod, "_get_token_bridge", lambda: fake_bridge)

    fake_event = {
        "id": "evt_billing_trace",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_billing_trace",
                "mode": "subscription",
                "payment_status": "paid",
                "subscription": "sub_billing_trace",
                "currency": "usd",
                "amount_total": 1200,
                "metadata": {
                    "user_id": user.id,
                    "plan": "starter",
                    "bridge_x0t": "true",
                },
            }
        },
    }
    monkeypatch.setattr(
        billing_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: fake_event,
    )

    result = await billing_mod.stripe_webhook(
        _DummyRequest(event_bus=bus),
        db_session,
    )

    assert result["status"] == "success"
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="maas-billing",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["component"] == "api.maas_billing"
    assert payload["operation"] == "stripe_checkout_session_webhook"
    assert payload["stage"] == "subscription_activated"
    assert payload["service_name"] == "maas-billing"
    assert payload["source_alias"] == "maas-billing"
    assert payload["layer"] == "billing_webhook_to_commerce_bridge"
    assert payload["stripe_event_type"] == "checkout.session.completed"
    assert len(payload["stripe_event_id_hash"]) == 16
    assert len(payload["session_id_hash"]) == 16
    assert payload["session_id_present"] is True
    assert len(payload["user_id_hash"]) == 16
    assert len(payload["invoice_id_hash"]) == 16
    assert payload["plan"] == "starter"
    assert payload["amount_total"] == 1200
    assert payload["currency"] == "USD"
    assert payload["provider"] == "stripe"
    assert payload["bridge_x0t_requested"] is True
    assert payload["bridge_x0t_minted"] is True
    assert payload["local_db_write"] is True
    assert payload["duration_ms"] >= 0
    assert payload["raw_identifiers_redacted"] is True
    assert payload["settlement_evidence"]["source_quality"] == "stripe_webhook_event"
    assert payload["settlement_evidence"]["settlement_action"] == "webhook_local_mutation_only"
    assert payload["settlement_evidence"]["dataplane_confirmed"] is False
    assert payload["settlement_evidence"]["provider"] == "stripe"
    assert payload["settlement_evidence"]["payment_status"] == "paid"
    assert payload["settlement_evidence"]["live_provider_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["bank_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["chain_finality_confirmed"] is False
    assert payload["settlement_evidence"]["db_write_evidence"]["committed"] is True
    assert payload["settlement_evidence"]["bridge_evidence"]["attempted"] is True
    assert payload["settlement_evidence"]["bridge_evidence"]["status"] == "minted"
    assert payload["settlement_evidence"]["output_summary"]["invoice_status_after"] == "paid"
    assert "live Stripe settlement" in payload["claim_boundary"]

    trace_summary = event_trace_evidence_summary(payload)
    settlement_summary = trace_summary["settlement_evidence"]
    assert settlement_summary["present"] is True
    assert settlement_summary["provider"] == "stripe"
    assert settlement_summary["payment_status"] == "paid"
    assert settlement_summary["dataplane_confirmed"] is False
    assert settlement_summary["live_provider_settlement_confirmed"] is False
    assert settlement_summary["bank_settlement_confirmed"] is False
    assert settlement_summary["chain_finality_confirmed"] is False
    assert settlement_summary["db_write_evidence"]["committed"] is True
    assert settlement_summary["bridge_evidence"]["status"] == "minted"
    assert settlement_summary["output_summary"]["invoice_status_after"] == "paid"

    serialized_payload = json.dumps(payload, sort_keys=True)
    assert "evt_billing_trace" not in serialized_payload
    assert "cs_billing_trace" not in serialized_payload
    assert "sub_billing_trace" not in serialized_payload
    assert user.id not in serialized_payload
    assert user.email not in serialized_payload
