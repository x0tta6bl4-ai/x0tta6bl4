import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_billing as billing_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, Invoice, User


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


def _create_user(db_session, *, user_id: str = "webhook-early-user-secret") -> User:
    user = User(
        id=user_id,
        email="webhook-early@test.local",
        password_hash="test-hash",
        api_key="webhook-early-key",
        role="user",
        plan="free",
        stripe_customer_id="cus_webhook_early_secret",
    )
    db_session.add(user)
    db_session.commit()
    return user


async def _run_webhook_case(
    *,
    fake_event: dict,
    db_session,
    monkeypatch,
    tmp_path,
    case_name: str,
):
    bus = EventBus(str(tmp_path / case_name))
    monkeypatch.setattr(billing_mod, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(billing_mod, "record_audit_log", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        billing_mod.stripe.Webhook,
        "construct_event",
        lambda *_args, **_kwargs: fake_event,
    )

    result = await billing_mod.stripe_webhook(_DummyRequest(bus), db_session)
    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="maas-billing",
    )
    assert len(events) == 1
    return result, events[0].data


def _assert_common_redacted(payload: dict, *raw_values: str) -> str:
    assert payload["component"] == "api.maas_billing"
    assert payload["operation"] == "stripe_checkout_session_webhook"
    assert payload["service_name"] == "maas-billing"
    assert payload["source_alias"] == "maas-billing"
    assert payload["layer"] == "billing_webhook_to_commerce_bridge"
    assert payload["stripe_event_type"] == "checkout.session.completed"
    assert payload["raw_identifiers_redacted"] is True
    assert payload["settlement_evidence"]["source_quality"] == "stripe_webhook_event"
    assert payload["settlement_evidence"]["dataplane_confirmed"] is False
    assert payload["settlement_evidence"]["live_provider_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["bank_settlement_confirmed"] is False
    assert payload["settlement_evidence"]["chain_finality_confirmed"] is False
    assert payload["settlement_evidence"]["raw_identifiers_redacted"] is True
    serialized_payload = json.dumps(payload, sort_keys=True)
    for raw_value in raw_values:
        assert raw_value not in serialized_payload
    return serialized_payload


@pytest.mark.asyncio
async def test_checkout_webhook_payment_not_completed_publishes_redacted_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    stripe_event_id = "evt_payment_not_completed_secret"
    session_id = "cs_payment_not_completed_secret"
    invoice_id = "inv_payment_not_completed_secret"
    result, payload = await _run_webhook_case(
        fake_event={
            "id": stripe_event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "payment",
                    "payment_status": "unpaid",
                    "metadata": {"invoice_id": invoice_id},
                }
            },
        },
        db_session=db_session,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        case_name="payment_not_completed",
    )

    assert result == {"status": "success", "skipped": "payment_not_completed"}
    assert payload["stage"] == "payment_not_completed"
    assert payload["status"] == "skipped"
    assert payload["payment_status"] == "unpaid"
    assert len(payload["stripe_event_id_hash"]) == 16
    assert len(payload["session_id_hash"]) == 16
    assert len(payload["invoice_id_hash"]) == 16
    _assert_common_redacted(payload, stripe_event_id, session_id, invoice_id)


@pytest.mark.asyncio
async def test_checkout_webhook_idempotent_replay_publishes_redacted_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    user = _create_user(db_session)
    stripe_event_id = "evt_idempotent_replay_secret"
    session_id = "cs_idempotent_replay_secret"
    invoice_id = "inv_idempotent_replay_secret"
    invoice = Invoice(
        id=invoice_id,
        user_id=user.id,
        mesh_id="mesh-idempotent-secret",
        total_amount=1200,
        currency="USD",
        status="paid",
        stripe_session_id=session_id,
        period_start=datetime(2026, 5, 29, 0, 0, 0),
        period_end=datetime(2026, 5, 29, 1, 0, 0),
    )
    db_session.add(invoice)
    db_session.commit()

    result, payload = await _run_webhook_case(
        fake_event={
            "id": stripe_event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "subscription",
                    "payment_status": "paid",
                    "subscription": "sub_idempotent_replay_secret",
                    "metadata": {"user_id": user.id, "plan": "starter"},
                }
            },
        },
        db_session=db_session,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        case_name="idempotent_replay",
    )

    assert result == {"status": "success", "idempotent": True}
    assert payload["stage"] == "idempotent_replay"
    assert payload["status"] == "skipped"
    assert len(payload["user_id_hash"]) == 16
    assert len(payload["invoice_id_hash"]) == 16
    _assert_common_redacted(
        payload,
        stripe_event_id,
        session_id,
        invoice_id,
        user.id,
        user.email,
    )


@pytest.mark.asyncio
async def test_checkout_webhook_missing_session_id_publishes_redacted_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    stripe_event_id = "evt_missing_session_secret"
    user_id = "missing-session-user-secret"
    result, payload = await _run_webhook_case(
        fake_event={
            "id": stripe_event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "subscription",
                    "payment_status": "paid",
                    "metadata": {"user_id": user_id, "plan": "starter"},
                }
            },
        },
        db_session=db_session,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        case_name="missing_session_id",
    )

    assert result == {"status": "error", "reason": "missing_session_id"}
    assert payload["stage"] == "missing_session_id"
    assert payload["status"] == "failed"
    assert payload["session_id_present"] is False
    assert len(payload["user_id_hash"]) == 16
    _assert_common_redacted(payload, stripe_event_id, user_id)


@pytest.mark.asyncio
async def test_checkout_webhook_user_not_found_publishes_redacted_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    stripe_event_id = "evt_user_not_found_secret"
    session_id = "cs_user_not_found_secret"
    customer_id = "cus_user_not_found_secret"
    subscription_id = "sub_user_not_found_secret"
    user_id = "metadata-user-not-found-secret"
    result, payload = await _run_webhook_case(
        fake_event={
            "id": stripe_event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "subscription",
                    "payment_status": "paid",
                    "customer": customer_id,
                    "subscription": subscription_id,
                    "metadata": {"user_id": user_id, "plan": "starter"},
                }
            },
        },
        db_session=db_session,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        case_name="user_not_found",
    )

    assert result == {"status": "error", "reason": "user_not_found"}
    assert payload["stage"] == "user_not_found"
    assert payload["status"] == "failed"
    assert len(payload["stripe_customer_id_hash"]) == 16
    assert len(payload["stripe_subscription_id_hash"]) == 16
    _assert_common_redacted(
        payload,
        stripe_event_id,
        session_id,
        customer_id,
        subscription_id,
        user_id,
    )


@pytest.mark.asyncio
async def test_checkout_webhook_invalid_plan_publishes_redacted_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    user = _create_user(db_session)
    stripe_event_id = "evt_invalid_plan_secret"
    session_id = "cs_invalid_plan_secret"
    invalid_plan = "evil-plan-secret"
    result, payload = await _run_webhook_case(
        fake_event={
            "id": stripe_event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "subscription",
                    "payment_status": "paid",
                    "subscription": "sub_invalid_plan_secret",
                    "metadata": {"user_id": user.id, "plan": invalid_plan},
                }
            },
        },
        db_session=db_session,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        case_name="invalid_plan",
    )

    assert result == {"status": "error", "reason": "invalid_plan"}
    assert payload["stage"] == "invalid_plan"
    assert payload["status"] == "failed"
    assert payload["plan"] is None
    _assert_common_redacted(
        payload,
        stripe_event_id,
        session_id,
        invalid_plan,
        user.id,
        user.email,
    )


@pytest.mark.asyncio
async def test_checkout_webhook_invoice_not_found_publishes_redacted_event(
    db_session,
    monkeypatch,
    tmp_path,
):
    stripe_event_id = "evt_invoice_not_found_secret"
    session_id = "cs_invoice_not_found_secret"
    invoice_id = "inv_invoice_not_found_secret"
    result, payload = await _run_webhook_case(
        fake_event={
            "id": stripe_event_id,
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": session_id,
                    "mode": "payment",
                    "payment_status": "paid",
                    "amount_total": 4500,
                    "currency": "usd",
                    "metadata": {"invoice_id": invoice_id},
                }
            },
        },
        db_session=db_session,
        monkeypatch=monkeypatch,
        tmp_path=tmp_path,
        case_name="invoice_not_found",
    )

    assert result == {"status": "success"}
    assert payload["stage"] == "invoice_not_found"
    assert payload["status"] == "failed"
    assert payload["amount_total"] == 4500
    assert payload["currency"] == "USD"
    assert len(payload["invoice_id_hash"]) == 16
    _assert_common_redacted(payload, stripe_event_id, session_id, invoice_id)
