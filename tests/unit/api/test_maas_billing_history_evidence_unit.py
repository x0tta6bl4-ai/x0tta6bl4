import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_billing as billing_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, Invoice, User


class _DummyRequest:
    def __init__(self, event_bus: EventBus):
        self.state = SimpleNamespace(event_bus=event_bus)


def _db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_list_invoices_publishes_redacted_history_observation(tmp_path):
    db = _db_session()
    try:
        user_id = "history-user-secret"
        mesh_id = "history-mesh-secret"
        invoice_id = "history-invoice-secret"
        stripe_session_id = "cs_history_secret"
        user = User(
            id=user_id,
            email="history-evidence@test.local",
            password_hash="test-hash",
            api_key="history-evidence-key",
            role="user",
            plan="starter",
        )
        invoice = Invoice(
            id=invoice_id,
            user_id=user_id,
            mesh_id=mesh_id,
            total_amount=1234,
            currency="USD",
            status="issued",
            stripe_session_id=stripe_session_id,
            period_start=datetime(2026, 5, 29, 0, 0, 0),
            period_end=datetime(2026, 5, 29, 1, 0, 0),
        )
        db.add(user)
        db.add(invoice)
        db.commit()

        bus = EventBus(str(tmp_path))
        response = asyncio.run(
            billing_mod.list_invoices(
                _DummyRequest(bus),
                current_user=user,
                db=db,
            )
        )

        assert len(response) == 1
        assert response[0].id == invoice_id
        assert response[0].mesh_id == mesh_id
        assert response[0].total_amount == 12.34

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-history",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["component"] == "api.maas_billing"
        assert payload["operation"] == "list_invoices"
        assert payload["stage"] == "observed_state"
        assert payload["status"] == "success"
        assert payload["service_name"] == "maas-billing"
        assert payload["source_alias"] == "maas-billing-history"
        assert payload["layer"] == "billing_history_observed_state"
        assert payload["read_only"] is True
        assert payload["observed_state"] is True
        assert payload["safe_actuator"] is False
        assert payload["history_summary"]["invoice_count"] == 1
        assert payload["history_summary"]["status_counts"] == {"issued": 1}
        assert payload["history_summary"]["currencies"] == ["USD"]
        assert payload["history_summary"]["total_amount_cents"] == 1234
        assert payload["history_summary"]["with_stripe_session_count"] == 1
        assert payload["raw_identifiers_redacted"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert mesh_id not in serialized_payload
        assert invoice_id not in serialized_payload
        assert stripe_session_id not in serialized_payload
    finally:
        db.close()
