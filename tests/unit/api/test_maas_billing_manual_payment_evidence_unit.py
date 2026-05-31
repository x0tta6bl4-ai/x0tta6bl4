import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
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


def test_pay_invoice_manual_publishes_redacted_manual_payment_event(tmp_path):
    db = _db_session()
    try:
        user_id = "manual-pay-user-secret"
        mesh_id = "manual-pay-mesh-secret"
        invoice_id = "manual-pay-invoice-secret"
        user = User(
            id=user_id,
            email="manual-pay@test.local",
            password_hash="test-hash",
            api_key="manual-pay-key",
            role="user",
            plan="starter",
        )
        invoice = Invoice(
            id=invoice_id,
            user_id=user_id,
            mesh_id=mesh_id,
            total_amount=2500,
            currency="USD",
            status="issued",
            period_start=datetime(2026, 5, 29, 0, 0, 0),
            period_end=datetime(2026, 5, 29, 1, 0, 0),
        )
        db.add(user)
        db.add(invoice)
        db.commit()

        bus = EventBus(str(tmp_path))
        response = asyncio.run(
            billing_mod.pay_invoice_manual(
                invoice_id,
                _DummyRequest(bus),
                current_user=user,
                db=db,
            )
        )

        assert response == {"status": "paid", "invoice_id": invoice_id}
        assert invoice.status == "paid"

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-manual-payment",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["component"] == "api.maas_billing"
        assert payload["operation"] == "pay_invoice_manual"
        assert payload["stage"] == "manual_payment_recorded"
        assert payload["status"] == "success"
        assert payload["service_name"] == "maas-billing"
        assert payload["source_alias"] == "maas-billing-manual-payment"
        assert payload["layer"] == "billing_manual_payment_mock"
        assert payload["provider"] == "local_mock"
        assert payload["invoice_status_before"] == "issued"
        assert payload["invoice_status_after"] == "paid"
        assert payload["amount_total"] == 2500
        assert payload["currency"] == "USD"
        assert payload["local_db_write"] is True
        assert len(payload["user_id_hash"]) == 16
        assert len(payload["invoice_id_hash"]) == 16
        assert len(payload["mesh_id_hash"]) == 16
        assert payload["raw_identifiers_redacted"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert mesh_id not in serialized_payload
        assert invoice_id not in serialized_payload
        assert user.email not in serialized_payload
    finally:
        db.close()


def test_pay_invoice_manual_missing_invoice_publishes_redacted_event(tmp_path):
    db = _db_session()
    try:
        user_id = "manual-pay-missing-user-secret"
        invoice_id = "manual-pay-missing-invoice-secret"
        user = User(
            id=user_id,
            email="manual-pay-missing@test.local",
            password_hash="test-hash",
            api_key="manual-pay-missing-key",
            role="user",
            plan="starter",
        )
        db.add(user)
        db.commit()

        bus = EventBus(str(tmp_path))
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                billing_mod.pay_invoice_manual(
                    invoice_id,
                    _DummyRequest(bus),
                    current_user=user,
                    db=db,
                )
            )

        assert exc_info.value.status_code == 404
        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-manual-payment",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["stage"] == "invoice_not_found"
        assert payload["status"] == "failed"
        assert payload["local_db_write"] is False
        assert payload["raw_identifiers_redacted"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert invoice_id not in serialized_payload
    finally:
        db.close()
