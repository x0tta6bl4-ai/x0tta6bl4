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


class _UsageService:
    def __init__(self, mesh_id: str, node_id: str):
        self.mesh_id = mesh_id
        self.node_id = node_id

    def get_mesh_usage(self, _instance):
        return {
            "mesh_id": self.mesh_id,
            "mesh_name": "secret-invoice-mesh",
            "status": "active",
            "active_nodes": 1,
            "total_node_hours": 2.0,
            "billing_period_start": "2026-05-29T00:00:00",
            "billing_period_end": "2026-05-29T02:00:00",
            "nodes": [{"node_id": self.node_id, "hours": 2.0}],
        }


def _db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_generate_invoice_publishes_redacted_invoice_event(monkeypatch, tmp_path):
    db = _db_session()
    try:
        user_id = "invoice-user-secret"
        mesh_id = "invoice-mesh-secret"
        node_id = "invoice-node-secret"
        user = User(
            id=user_id,
            email="invoice-evidence@test.local",
            password_hash="test-hash",
            api_key="invoice-evidence-key",
            role="user",
            plan="starter",
        )
        db.add(user)
        db.commit()

        monkeypatch.setattr(
            billing_mod,
            "_get_mesh_or_404",
            lambda raw_mesh_id, raw_owner_id: SimpleNamespace(
                mesh_id=raw_mesh_id,
                owner_id=raw_owner_id,
            ),
        )
        monkeypatch.setattr(
            billing_mod,
            "usage_metering_service",
            _UsageService(mesh_id, node_id),
        )
        bus = EventBus(str(tmp_path))

        response = asyncio.run(
            billing_mod.generate_invoice(
                mesh_id,
                _DummyRequest(bus),
                current_user=user,
                db=db,
            )
        )

        stored_invoice = db.query(Invoice).filter(Invoice.id == response.id).first()
        assert stored_invoice is not None
        assert stored_invoice.user_id == user_id
        assert stored_invoice.mesh_id == mesh_id
        assert stored_invoice.status == "issued"
        assert response.total_amount == 0.5
        assert isinstance(stored_invoice.period_start, datetime)

        events = bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-billing-invoice",
        )
        assert len(events) == 1
        payload = events[0].data
        assert payload["component"] == "api.maas_billing"
        assert payload["operation"] == "generate_invoice"
        assert payload["stage"] == "invoice_generated"
        assert payload["status"] == "success"
        assert payload["service_name"] == "maas-billing"
        assert payload["source_alias"] == "maas-billing-invoice"
        assert payload["layer"] == "billing_invoice_generation"
        assert payload["subtotal_cents"] == 50
        assert payload["minimum_invoice_applied"] is True
        assert payload["local_db_write"] is True
        assert payload["usage_summary"]["active_nodes"] == 1
        assert payload["usage_summary"]["node_entries"] == 1
        assert payload["raw_identifiers_redacted"] is True

        serialized_payload = json.dumps(payload, sort_keys=True)
        assert user_id not in serialized_payload
        assert mesh_id not in serialized_payload
        assert node_id not in serialized_payload
        assert response.id not in serialized_payload
        assert "secret-invoice-mesh" not in serialized_payload
    finally:
        db.close()
