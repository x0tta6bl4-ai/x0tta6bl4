import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_billing as billing_mod
import src.api.maas_marketplace as marketplace_mod
from src.database import Base, Invoice, User


class _DummyRequest:
    def __init__(self, payload: bytes = b"{}", signature: str = "sig"):
        self._payload = payload
        self.headers = {"stripe-signature": signature}

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
