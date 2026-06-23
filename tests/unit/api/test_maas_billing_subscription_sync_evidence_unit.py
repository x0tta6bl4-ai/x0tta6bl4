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


class _StripeSubscription(dict):
    def __init__(self):
        super().__init__(
            {
                "id": "sub_subscription_sync_secret",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_pro_sync_secret"}}]},
            }
        )
        self.id = "sub_subscription_sync_secret"
        self.status = "active"


def _db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_sync_subscription_with_stripe_publishes_redacted_sync_event(
    monkeypatch,
    tmp_path,
):
    db = _db_session()
    try:
        user_id = "subscription-sync-user-secret"
        stripe_customer_id = "cus_subscription_sync_secret"
        stripe_subscription_id = "sub_subscription_sync_secret"
        price_id = "price_pro_sync_secret"
        user = User(
            id=user_id,
            email="subscription-sync@test.local",
            password_hash="test-hash",
            api_key="subscription-sync-key",
            role="user",
            plan="starter",
            stripe_customer_id=stripe_customer_id,
        )
        db.add(user)
        db.commit()

        async def _execute_stripe_call(_operation, **_kwargs):
            return SimpleNamespace(data=[_StripeSubscription()])

        monkeypatch.setattr(billing_mod, "STRIPE_SECRET_KEY", "sk_test_sync")
        monkeypatch.setattr(
            billing_mod,
            "STRIPE_PLANS",
            {"starter": "price_starter", "pro": price_id, "enterprise": "price_ent"},
        )
        monkeypatch.setattr(billing_mod, "_execute_stripe_call", _execute_stripe_call)

        bus = EventBus(str(tmp_path))
        asyncio.run(
            billing_mod.sync_subscription_with_stripe(
                user,
                db,
                request=_DummyRequest(bus),
            )
        )

        assert user.plan == "pro"
        assert user.stripe_subscription_id == stripe_subscription_id

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-subscription-sync",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["component"] == "api.maas_billing"
        assert payload["operation"] == "sync_subscription_with_stripe"
        assert payload["stage"] == "subscription_synced"
        assert payload["status"] == "success"
        assert payload["service_name"] == "maas-billing"
        assert payload["source_alias"] == "maas-billing-subscription-sync"
        assert payload["layer"] == "billing_subscription_sync"
        assert payload["provider"] == "stripe"
        assert payload["stripe_configured"] is True
        assert payload["local_db_write"] is True
        assert payload["plan_before"] == "starter"
        assert payload["plan_after"] == "pro"
        assert payload["subscription_status"] == "active"
        assert len(payload["user_id_hash"]) == 16
        assert len(payload["stripe_customer_id_hash"]) == 16
        assert len(payload["stripe_subscription_id_hash"]) == 16
        assert len(payload["price_id_hash"]) == 16
        assert payload["raw_identifiers_redacted"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert stripe_customer_id not in serialized_payload
        assert stripe_subscription_id not in serialized_payload
        assert price_id not in serialized_payload
    finally:
        db.close()
