from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@dataclass
class _FakeChunk:
    text: str
    metadata: dict


@pytest.fixture
def app_and_rag():
    rag = MagicMock()
    rag.is_indexed.return_value = True
    rag.is_verification_indexed.return_value = False
    rag.index_verification_evidence = AsyncMock(return_value=True)
    rag.index_event_traces = AsyncMock(return_value=True)
    rag.verification_evidence_status.return_value = {
        "verification_root": "/mnt/projects/docs/verification",
        "root_exists": True,
        "indexable_files": 2,
        "indexed": False,
        "indexed_files": 0,
        "indexed_chunks": 0,
        "source": "docs/verification",
    }
    rag.event_trace_status.return_value = {
        "source": "EventBus",
        "source_class": "event_trace",
        "relative_path": ".agent_coordination/events.log",
        "indexed": True,
        "indexed_events": 1,
        "indexed_chunks": 1,
        "redacted": True,
    }
    rag.query = AsyncMock()

    with patch("src.api.ledger_endpoints.get_ledger_rag", return_value=rag):
        from src.api.ledger_endpoints import router

        app = FastAPI()
        app.include_router(router)
        yield app, rag


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_verification_evidence_status_endpoint(app_and_rag):
    app, rag = app_and_rag

    async with _client(app) as client:
        response = await client.get("/api/v1/ledger/evidence/status")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "docs/verification"
    assert body["indexable_files"] == 2
    rag.verification_evidence_status.assert_called_once_with()


@pytest.mark.asyncio
async def test_verification_evidence_index_endpoint(app_and_rag):
    app, rag = app_and_rag
    rag.verification_evidence_status.return_value = {
        **rag.verification_evidence_status.return_value,
        "indexed": True,
        "indexed_files": 2,
        "indexed_chunks": 4,
    }

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/evidence/index",
            params={"force": True, "max_files": 2},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["verification_evidence"]["index_success"] is True
    rag.index_verification_evidence.assert_awaited_once_with(force=True, max_files=2)


@pytest.mark.asyncio
async def test_search_can_explicitly_index_verification_evidence(app_and_rag):
    app, rag = app_and_rag
    result = MagicMock()
    result.query = "proof gate"
    result.results = [
            {
                "text": "proof gate passed",
                "score": 0.9,
                "metadata": {
                    "source": "docs/verification",
                    "source_class": "verification_evidence",
                    "relative_path": "docs/verification/proof-gate/summary.json",
                    "file_suffix": ".json",
                    "latest_alias": False,
                    "document_id": "verification_proof_gate",
                    "chunk_id": "chunk-1",
                },
                "section": "proof",
            }
        ]
    result.total_results = 1
    result.search_time_ms = 3.0
    result.metadata = {"engine": "test"}
    rag.query.return_value = result

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/search",
            json={
                "query": "proof gate",
                "top_k": 3,
                "include_verification": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["metadata"]["source"] == "docs/verification"
    assert body["metadata"]["citations"] == [
        {
            "source": "docs/verification",
            "source_class": "verification_evidence",
            "relative_path": "docs/verification/proof-gate/summary.json",
            "title": "proof",
            "section": "proof",
            "document_id": "verification_proof_gate",
            "chunk_id": "chunk-1",
            "file_suffix": ".json",
            "latest_alias": False,
            "score": 0.9,
        }
    ]
    rag.index_verification_evidence.assert_awaited_once_with()
    rag.query.assert_awaited_once_with("proof gate", top_k=3)


@pytest.mark.asyncio
async def test_event_trace_index_endpoint_indexes_redacted_trace_payload(
    app_and_rag,
    monkeypatch,
):
    app, rag = app_and_rag
    trace_payload = {
        "status": "ok",
        "redacted": True,
        "filter": {
            "service_name": "swarm-pbft",
            "layer": None,
            "source_agents": ["swarm-pbft"],
        },
        "events_total": 1,
        "events": [
            {
                "event_id": "event-1",
                "event_type": "pipeline.stage_start",
                "source_agent": "swarm-pbft",
                "data": {"spiffe_id": "[redacted]"},
                "redacted": True,
            }
        ],
    }

    monkeypatch.setattr(
        "src.api.ledger_endpoints.EventBus",
        lambda project_root=".": object(),
    )
    monkeypatch.setattr(
        "src.api.ledger_endpoints.service_event_trace_history",
        lambda bus, **kwargs: trace_payload,
    )

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/event-traces/index",
            params={"service_name": "swarm-pbft", "limit": 10},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["event_traces"]["source_class"] == "event_trace"
    assert body["event_traces"]["trace_filter"]["source_agents"] == ["swarm-pbft"]
    assert body["event_traces"]["events_seen"] == 1
    rag.index_event_traces.assert_awaited_once_with(trace_payload, force=False)


@pytest.mark.asyncio
async def test_event_trace_citations_include_event_identity_metadata(app_and_rag):
    app, rag = app_and_rag
    result = MagicMock()
    result.query = "swarm event trace"
    result.results = [
        {
            "text": "redacted event trace",
            "score": 0.8,
            "metadata": {
                "source": "EventBus",
                "source_class": "event_trace",
                "relative_path": ".agent_coordination/events.log",
                "document_id": "event_trace_event_1",
                "chunk_id": "chunk-1",
                "event_id": "event-1",
                "event_type": "pipeline.stage_start",
                "source_agent": "swarm-pbft",
                "service_name": "swarm-pbft",
                "layer": "swarm_consensus_to_control_plane",
                "entrypoint": "src/swarm/pbft.py",
                "redacted": True,
            },
            "section": "swarm-pbft:pipeline.stage_start",
        }
    ]
    result.total_results = 1
    result.search_time_ms = 2.0
    result.metadata = {"engine": "test"}
    rag.query.return_value = result

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/search",
            json={"query": "swarm event trace", "top_k": 1},
        )

    assert response.status_code == 200
    citation = response.json()["metadata"]["citations"][0]
    assert citation["source"] == "EventBus"
    assert citation["source_class"] == "event_trace"
    assert citation["event_id"] == "event-1"
    assert citation["source_agent"] == "swarm-pbft"
    assert citation["layer"] == "swarm_consensus_to_control_plane"
    assert citation["entrypoint"] == "src/swarm/pbft.py"
    assert citation["redacted"] is True
