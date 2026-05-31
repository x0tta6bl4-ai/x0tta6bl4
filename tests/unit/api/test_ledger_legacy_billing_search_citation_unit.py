import json
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api import ledger_endpoints
import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus
from src.database import Base, User
from src.ledger.rag_search import LedgerRAGSearch


class _DummyLegacyBillingRequest:
    def __init__(self, payload: bytes, event_bus: EventBus):
        self._payload = payload
        self.state = SimpleNamespace(event_bus=event_bus)

    async def body(self) -> bytes:
        return self._payload


class _ApiFakeRAG:
    def __init__(self):
        self.documents = []

    def add_document(self, text: str, document_id: str, metadata: dict):
        chunk_id = f"{document_id}:chunk-0"
        self.documents.append(
            {
                "text": text,
                "document_id": document_id,
                "metadata": {
                    **metadata,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                },
            }
        )
        return [chunk_id]

    def retrieve(self, _question: str, top_k: int = 10):
        selected = self.documents[:top_k]
        return SimpleNamespace(
            retrieved_chunks=[
                SimpleNamespace(text=document["text"], metadata=document["metadata"])
                for document in selected
            ],
            scores=[1.0 for _document in selected],
            retrieval_time_ms=0.0,
            rerank_time_ms=0.0,
        )


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


def _build_ledger(tmp_path):
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger.rag = _ApiFakeRAG()
    ledger._indexed = True
    return ledger


@pytest.mark.asyncio
async def test_legacy_billing_eventbus_trace_reaches_ledger_search_citation(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.delenv("X0T_BILLING_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", raising=False)

    user = User(
        id=f"usr-{uuid.uuid4().hex[:8]}",
        email=f"legacy-search-{uuid.uuid4().hex[:8]}@test.local",
        password_hash="test-hash",
        api_key=f"key-{uuid.uuid4().hex}",
        role="user",
        plan="starter",
    )
    db_session.add(user)
    db_session.commit()

    raw_event_id = f"evt_legacy_search_{uuid.uuid4().hex}"
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
    ledger = _build_ledger(tmp_path)

    result = await legacy_mod.legacy_billing_webhook(
        legacy_mod.BillingWebhookRequest(**payload),
        _DummyLegacyBillingRequest(raw_payload, bus),
        db_session,
    )
    assert result["processed"] is True

    monkeypatch.setattr(ledger_endpoints, "get_ledger_rag", lambda: ledger)
    monkeypatch.setattr(ledger_endpoints, "EventBus", lambda project_root=".": bus)

    app = FastAPI()
    app.include_router(ledger_endpoints.router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://ledger-test.local",
    ) as client:
        index_response = await client.post(
            "/api/v1/ledger/event-traces/index",
            params={
                "service_name": "maas-billing",
                "event_type": "pipeline.stage_end",
                "limit": 10,
            },
        )
        search_response = await client.post(
            "/api/v1/ledger/search",
            json={"query": "maas legacy billing webhook event trace", "top_k": 5},
        )

    assert index_response.status_code == 200
    index_payload = index_response.json()
    assert index_payload["event_traces"]["events_seen"] >= 1
    expected_source_agents = {
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
    }
    assert expected_source_agents.issubset(
        set(index_payload["event_traces"]["trace_filter"]["source_agents"])
    )

    assert search_response.status_code == 200
    search_payload = search_response.json()
    citations = search_payload["metadata"]["citations"]
    legacy_citation = next(
        citation
        for citation in citations
        if citation.get("source_agent") == "maas-legacy-billing"
    )
    assert legacy_citation["source"] == "EventBus"
    assert legacy_citation["source_class"] == "event_trace"
    assert legacy_citation["service_name"] == "maas-billing"
    assert legacy_citation["layer"] == "billing_webhook_to_commerce_bridge"
    assert legacy_citation["entrypoint"] == "src/api/maas_legacy.py"
    assert legacy_citation["redacted"] is True

    response_text = json.dumps(search_payload, sort_keys=True)
    assert raw_event_id not in response_text
    assert raw_customer_id not in response_text
    assert raw_subscription_id not in response_text
    assert user.email not in response_text
