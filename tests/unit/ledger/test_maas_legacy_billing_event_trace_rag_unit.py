import json
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType
from src.database import Base, User
from src.ledger.rag_search import LedgerRAGSearch
from src.services.service_event_trace import service_event_trace_history


class _DummyRequest:
    def __init__(self, payload: bytes, event_bus: EventBus):
        self._payload = payload
        self.state = SimpleNamespace(event_bus=event_bus)

    async def body(self) -> bytes:
        return self._payload


class _FakeRAG:
    def __init__(self):
        self.documents = []

    def add_document(self, text: str, document_id: str, metadata: dict):
        self.documents.append(
            {"text": text, "document_id": document_id, "metadata": metadata}
        )
        return [f"{document_id}:chunk"]


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


@pytest.mark.asyncio
async def test_legacy_billing_event_trace_is_ledger_indexable_without_raw_ids(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv("X0T_BILLING_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", raising=False)

    user = User(
        id=f"usr-{uuid.uuid4().hex[:8]}",
        email=f"legacy-ledger-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="test-hash",
        api_key=f"key-{uuid.uuid4().hex}",
        role="user",
        plan="starter",
    )
    db_session.add(user)
    db_session.commit()

    raw_event_id = f"evt_legacy_ledger_{uuid.uuid4().hex}"
    raw_customer_id = f"cus_{uuid.uuid4().hex}"
    raw_subscription_id = f"sub_{uuid.uuid4().hex}"
    payload = {
        "event_id": raw_event_id,
        "event_type": "plan.upgraded",
        "plan": "pro",
        "user_id": user.id,
        "email": user.email,
        "customer_id": raw_customer_id,
        "subscription_id": raw_subscription_id,
    }
    raw_payload = json.dumps(payload).encode("utf-8")
    bus = EventBus(str(tmp_path))

    result = await legacy_mod.legacy_billing_webhook(
        legacy_mod.BillingWebhookRequest(**payload),
        _DummyRequest(raw_payload, bus),
        db_session,
    )
    assert result["processed"] is True

    trace_payload = service_event_trace_history(
        bus,
        service_name="maas-billing",
        event_type=EventType.PIPELINE_STAGE_END,
        limit=10,
    )
    trace_text = json.dumps(trace_payload, sort_keys=True, default=str)

    assert trace_payload["events_total"] == 1
    assert trace_payload["filter"]["source_agents"] == [
        "maas-billing",
        "maas-billing-checkout",
        "maas-billing-customer-portal",
        "maas-billing-history",
        "maas-billing-invoice",
        "maas-billing-manual-payment",
        "maas-billing-subscription-checkout",
        "maas-billing-subscription-sync",
        "maas-billing-subscription-webhook",
        "maas-legacy-billing",
        "maas-legacy-billing-usage",
    ]
    assert trace_payload["events"][0]["source_agent"] == "maas-legacy-billing"
    assert trace_payload["events"][0]["data"]["component"] == "api.maas_legacy"
    assert trace_payload["events"][0]["data"]["service_name"] == "maas-billing"
    assert raw_event_id not in trace_text
    assert raw_customer_id not in trace_text
    assert raw_subscription_id not in trace_text
    assert user.email not in trace_text

    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    success = await ledger.index_event_traces(trace_payload)

    assert success is True
    assert len(ledger.rag.documents) == 1
    document = ledger.rag.documents[0]
    metadata = document["metadata"]
    assert metadata["source"] == "EventBus"
    assert metadata["source_class"] == "event_trace"
    assert metadata["source_agent"] == "maas-legacy-billing"
    assert metadata["service_name"] == "maas-billing"
    assert metadata["layer"] == "billing_webhook_to_commerce_bridge"
    assert metadata["entrypoint"] == "src/api/maas_legacy.py"
    assert metadata["redacted"] is True
    assert raw_event_id not in document["text"]
    assert raw_customer_id not in document["text"]
    assert raw_subscription_id not in document["text"]
    assert user.email not in document["text"]
