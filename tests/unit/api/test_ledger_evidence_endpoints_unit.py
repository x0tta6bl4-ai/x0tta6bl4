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
    rag.is_current_evidence_indexed.return_value = False
    rag.index_verification_evidence = AsyncMock(return_value=True)
    rag.index_current_evidence = AsyncMock(return_value=True)
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
    rag.current_evidence_status.return_value = {
        "current_evidence_root": "/mnt/projects/docs/architecture",
        "root_exists": True,
        "indexable_files": 2,
        "indexed": True,
        "indexed_files": 2,
        "indexed_chunks": 4,
        "source": "docs/architecture",
        "claim_status_counts": {
            "current_active_audit": 1,
            "current_evidence_map": 1,
        },
    }
    rag.query = AsyncMock()

    with patch("src.api.ledger_endpoints.get_ledger_rag", return_value=rag):
        from src.api.ledger_endpoints import router

        app = FastAPI()
        app.include_router(router)
        yield app, rag


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def test_citation_claim_usage_gate_blocks_upstream_local_only_summaries():
    from src.api.ledger_endpoints import _citation_claim_usage_gate

    gate = _citation_claim_usage_gate(
        {
            "current_evidence": True,
            "historical_claim_inventory": False,
            "requires_current_evidence_context": False,
            "upstream_claim_gate_summary": {
                "present": True,
                "surface": "integration_spine.reward_context",
                "external_settlement_finality_claim_allowed": False,
                "payloads_redacted": True,
            },
            "upstream_cross_plane_claim_gate_summary": {
                "present": True,
                "surface": "integration_spine.reward_context",
                "allowed": False,
                "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
                "payloads_redacted": True,
            },
        },
        claim_sensitive_query=True,
        cross_plane_claim_gate={"available": True, "allowed": True},
    )

    assert gate is not None
    assert gate["standalone_claim_proof_allowed"] is False
    assert gate["claim_promotion_allowed"] is False
    assert gate["current_context_allowed"] is True
    assert gate["cross_plane_gate_allowed"] is True
    assert gate["upstream_claim_gate_present"] is True
    assert gate["upstream_cross_plane_claim_gate_present"] is True
    assert gate["upstream_cross_plane_gate_allowed"] is False
    assert gate["blockers"] == [
        "upstream_claim_gate_local_only_not_proof",
        "upstream_cross_plane_claim_gate_blocked",
    ]


def test_citation_claim_usage_gate_blocks_external_dpi_gap_record():
    from src.api.ledger_endpoints import _citation_claim_usage_gate

    gate = _citation_claim_usage_gate(
        {
            "current_evidence": False,
            "historical_claim_inventory": False,
            "requires_current_evidence_context": True,
            "external_evidence_gap_record": True,
            "external_dpi_intake_claim_gate_summary": {
                "present": True,
                "external_evidence_gap_record": True,
                "proof_gate_dpi_bypass_claim_allowed": False,
                "production_readiness_claim_allowed": False,
            },
        },
        claim_sensitive_query=True,
        cross_plane_claim_gate={"available": True, "allowed": True},
    )

    assert gate is not None
    assert gate["standalone_claim_proof_allowed"] is False
    assert gate["claim_promotion_allowed"] is False
    assert gate["current_context_allowed"] is False
    assert gate["cross_plane_gate_allowed"] is True
    assert gate["external_dpi_intake_claim_gate_present"] is True
    assert gate["external_evidence_gap_record"] is True
    assert gate["blockers"] == [
        "citation_requires_current_evidence_context",
        "citation_not_current_evidence",
        "external_evidence_gap_record_not_proof",
        "external_dpi_intake_citation_not_proof",
        "external_dpi_proof_gate_not_allowed",
    ]


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
async def test_search_citations_preserve_external_dpi_gap_record_gate(
    app_and_rag,
    monkeypatch,
):
    app, rag = app_and_rag

    def fake_cross_plane_gate(_root, *, claims):
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "summary": {"claims_total": len(claims)},
            "context": {"open_gap_ids": ["external-dpi-proof-missing"]},
            "claim_results": [
                {
                    "claim_id": claim_id,
                    "allowed": False,
                    "blockers": ["current_evidence_open_gaps"],
                }
                for claim_id in claims
            ],
            "claim_boundary": "local gate decision, not production proof",
        }

    monkeypatch.setattr(
        "src.api.ledger_endpoints.build_cross_plane_proof_gate_report",
        fake_cross_plane_gate,
    )
    result = MagicMock()
    result.query = "external dpi bypass"
    result.results = [
        {
            "text": "incoming dpi gap record",
            "score": 0.88,
            "claim_adjusted_score": 0.855,
            "metadata": {
                "source": "docs/verification",
                "source_class": "external_dpi_gap_record",
                "relative_path": "docs/verification/incoming/dpi_lab.json",
                "file_suffix": ".json",
                "document_id": "verification_dpi_lab",
                "chunk_id": "chunk-dpi-gap",
                "claim_status": "external_dpi_gap_record",
                "claim_scope": "external_dpi_gap_record_not_proof",
                "current_evidence": False,
                "historical_claim_inventory": False,
                "requires_current_evidence_context": True,
                "runtime_memory_priority": 10,
                "external_evidence_gap_record": True,
                "external_dpi_intake_claim_gate_summary": {
                    "present": True,
                    "schema": (
                        "x0tta6bl4.external_dpi_intake."
                        "ledger_citation_claim_gate.v1"
                    ),
                    "external_evidence_gap_record": True,
                    "candidate_file_observed_claim_allowed": True,
                    "proof_gate_dpi_bypass_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "this_citation_is_proof": False,
                },
            },
            "section": "dpi_lab",
        }
    ]
    result.total_results = 1
    result.search_time_ms = 3.0
    result.metadata = {"engine": "test"}
    rag.query.return_value = result

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/search",
            json={"query": "external dpi bypass", "top_k": 3},
        )

    assert response.status_code == 200
    body = response.json()
    citation = body["metadata"]["citations"][0]
    assert citation["claim_status"] == "external_dpi_gap_record"
    assert citation["external_evidence_gap_record"] is True
    gate_summary = citation["external_dpi_intake_claim_gate_summary"]
    assert gate_summary["candidate_file_observed_claim_allowed"] is True
    assert gate_summary["proof_gate_dpi_bypass_claim_allowed"] is False
    assert gate_summary["production_readiness_claim_allowed"] is False
    usage_gate = citation["claim_usage_gate"]
    assert usage_gate["standalone_claim_proof_allowed"] is False
    assert usage_gate["external_dpi_intake_claim_gate_present"] is True
    assert usage_gate["external_evidence_gap_record"] is True
    assert usage_gate["blockers"] == [
        "citation_requires_current_evidence_context",
        "citation_not_current_evidence",
        "cross_plane_claim_gate_blocked",
        "external_evidence_gap_record_not_proof",
        "external_dpi_intake_citation_not_proof",
        "external_dpi_proof_gate_not_allowed",
    ]
    citation_gate = body["metadata"]["claim_sensitive_citation_gate"]
    assert citation_gate["external_dpi_intake_citations"] == 1
    assert citation_gate["external_evidence_gap_record_citations"] == 1
    rag.index_current_evidence.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_search_can_include_current_evidence_maps(app_and_rag):
    app, rag = app_and_rag
    result = MagicMock()
    result.query = "production readiness current evidence"
    result.results = [
        {
            "text": "working map, not production readiness proof",
            "score": 0.71,
            "claim_adjusted_score": 0.7575,
            "metadata": {
                "source": "docs/architecture",
                "source_class": "architecture_current_evidence_map",
                "relative_path": (
                    "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
                ),
                "file_suffix": ".json",
                "latest_alias": False,
                "document_id": "verification_current_cross_plane",
                "chunk_id": "chunk-current",
                "claim_status": "current_evidence_map",
                "claim_scope": "current_working_map_not_production_proof",
                "current_evidence": True,
                "historical_claim_inventory": False,
                "requires_current_evidence_context": False,
                "runtime_memory_priority": 95,
            },
            "section": "CURRENT_CROSS_PLANE_EVIDENCE_MAP",
        }
    ]
    result.total_results = 1
    result.search_time_ms = 4.0
    result.metadata = {"engine": "test"}
    rag.query.return_value = result

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/search",
            json={
                "query": "production readiness current evidence",
                "top_k": 5,
                "include_current_evidence": True,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["current_evidence"]["source"] == "docs/architecture"
    assert body["metadata"]["current_evidence"]["claim_status_counts"] == {
        "current_active_audit": 1,
        "current_evidence_map": 1,
    }
    citation = body["metadata"]["citations"][0]
    assert citation["source"] == "docs/architecture"
    assert citation["claim_status"] == "current_evidence_map"
    assert citation["claim_scope"] == "current_working_map_not_production_proof"
    assert citation["current_evidence"] is True
    assert citation["historical_claim_inventory"] is False
    assert citation["requires_current_evidence_context"] is False
    assert citation["runtime_memory_priority"] == 95
    assert citation["claim_adjusted_score"] == 0.7575
    rag.index_current_evidence.assert_awaited_once_with()
    rag.query.assert_awaited_once_with(
        "production readiness current evidence",
        top_k=5,
    )


@pytest.mark.asyncio
async def test_search_auto_includes_current_evidence_for_claim_sensitive_query(
    app_and_rag,
    monkeypatch,
):
    app, rag = app_and_rag
    captured_gate = {}

    def fake_cross_plane_gate(root, *, claims):
        captured_gate["root"] = root
        captured_gate["claims"] = claims
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "summary": {
                "claims_total": len(claims),
                "claims_allowed": 0,
                "claims_blocked": len(claims),
            },
            "context": {
                "open_gap_ids": ["external-dpi-proof-missing"],
                "next_action_ids": ["external-dpi-real-artifact-intake"],
            },
            "claim_results": [
                {
                    "claim_id": claim_id,
                    "allowed": False,
                    "blockers": ["current_evidence_open_gaps"],
                }
                for claim_id in claims
            ],
            "claim_boundary": "local gate decision, not production proof",
        }

    monkeypatch.setattr(
        "src.api.ledger_endpoints.build_cross_plane_proof_gate_report",
        fake_cross_plane_gate,
    )
    result = MagicMock()
    result.query = "is x0tta6bl4 production ready"
    result.results = [
        {
            "text": "current audit says production readiness is not proven",
            "score": 0.72,
            "claim_adjusted_score": 0.77,
            "metadata": {
                "source": "docs/architecture",
                "source_class": "architecture_current_audit",
                "relative_path": "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
                "document_id": "current_active_goal_gap_audit",
                "chunk_id": "chunk-audit",
                "claim_status": "current_active_audit",
                "claim_scope": "current_working_audit_not_production_proof",
                "current_evidence": True,
                "historical_claim_inventory": False,
                "requires_current_evidence_context": False,
                "runtime_memory_priority": 100,
            },
            "section": "CURRENT_ACTIVE_GOAL_GAP_AUDIT",
        },
        {
            "text": "old completion report claimed production ready",
            "score": 0.91,
            "claim_adjusted_score": 0.91,
            "metadata": {
                "source": "docs/05-operations",
                "source_class": "historical_operations_claim_inventory",
                "relative_path": "docs/05-operations/project-completion-report-v1.5.md",
                "document_id": "project_completion_report_v1_5",
                "chunk_id": "chunk-historical",
                "claim_status": "historical_claim_inventory",
                "claim_scope": "historical_or_claim_material_requires_current_evidence",
                "current_evidence": False,
                "historical_claim_inventory": True,
                "requires_current_evidence_context": True,
                "runtime_memory_priority": 20,
            },
            "section": "project-completion-report-v1.5",
        },
    ]
    result.total_results = 2
    result.search_time_ms = 4.0
    result.metadata = {"engine": "test"}
    rag.query.return_value = result

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/search",
            json={
                "query": "is x0tta6bl4 production ready",
                "top_k": 5,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["current_evidence"]["source"] == "docs/architecture"
    assert body["metadata"]["current_evidence_context"] == {
        "included": True,
        "reason": "claim_sensitive_query",
        "claim_sensitive_query": True,
        "explicit_request": False,
        "claim_boundary": (
            "Current architecture evidence maps/audit are search context, not proof "
            "that the requested production, dataplane, trust, DPI, or settlement "
            "claim is true."
        ),
    }
    claim_gate = body["metadata"]["cross_plane_claim_gate"]
    assert claim_gate["decision"] == "CROSS_PLANE_CLAIMS_BLOCKED"
    assert claim_gate["allowed"] is False
    assert claim_gate["available"] is True
    assert claim_gate["requested_claim_ids"] == ["production_readiness"]
    assert claim_gate["claim_results"][0]["blockers"] == [
        "current_evidence_open_gaps"
    ]
    assert captured_gate["claims"] == ("production_readiness",)
    citation = body["metadata"]["citations"][0]
    assert citation["claim_status"] == "current_active_audit"
    assert citation["current_evidence"] is True
    assert citation["claim_usage_gate"]["standalone_claim_proof_allowed"] is False
    assert citation["claim_usage_gate"]["claim_promotion_allowed"] is False
    assert citation["claim_usage_gate"]["current_context_allowed"] is True
    assert citation["claim_usage_gate"]["blockers"] == [
        "cross_plane_claim_gate_blocked"
    ]
    historical = body["metadata"]["citations"][1]
    assert historical["claim_status"] == "historical_claim_inventory"
    assert historical["claim_usage_gate"]["standalone_claim_proof_allowed"] is False
    assert historical["claim_usage_gate"]["claim_promotion_allowed"] is False
    assert historical["claim_usage_gate"]["current_context_allowed"] is False
    assert historical["claim_usage_gate"]["blockers"] == [
        "historical_claim_inventory_not_proof",
        "citation_requires_current_evidence_context",
        "citation_not_current_evidence",
        "cross_plane_claim_gate_blocked",
    ]
    citation_gate = body["metadata"]["claim_sensitive_citation_gate"]
    assert citation_gate["citations_total"] == 2
    assert citation_gate["blocked_citations"] == 2
    assert citation_gate["historical_claim_inventory_citations"] == 1
    assert citation_gate["current_evidence_citations"] == 1
    rag.index_current_evidence.assert_awaited_once_with()
    rag.query.assert_awaited_once_with(
        "is x0tta6bl4 production ready",
        top_k=5,
    )


@pytest.mark.asyncio
async def test_search_claim_gate_infers_dataplane_dpi_and_settlement_claims(
    app_and_rag,
    monkeypatch,
):
    app, rag = app_and_rag
    captured_gate = {}

    def fake_cross_plane_gate(root, *, claims):
        captured_gate["claims"] = claims
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "summary": {"claims_total": len(claims)},
            "context": {"open_gap_ids": ["external-dpi-proof-missing"]},
            "claim_results": [
                {"claim_id": claim_id, "allowed": False, "blockers": []}
                for claim_id in claims
            ],
            "claim_boundary": "local gate decision, not production proof",
        }

    monkeypatch.setattr(
        "src.api.ledger_endpoints.build_cross_plane_proof_gate_report",
        fake_cross_plane_gate,
    )
    result = MagicMock()
    result.query = "dataplane DPI bypass settlement finality"
    result.results = []
    result.total_results = 0
    result.search_time_ms = 1.0
    result.metadata = {"engine": "test"}
    rag.query.return_value = result

    async with _client(app) as client:
        response = await client.post(
            "/api/v1/ledger/search",
            json={
                "query": "dataplane DPI bypass settlement finality",
                "top_k": 3,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["cross_plane_claim_gate"]["requested_claim_ids"] == [
        "dataplane_delivery",
        "settlement_finality",
        "dpi_bypass",
    ]
    assert captured_gate["claims"] == (
        "dataplane_delivery",
        "settlement_finality",
        "dpi_bypass",
    )


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
                "evidence_summary": {
                    "available": True,
                    "claim_boundary_summary": {
                        "present": True,
                        "claim_boundaries": [
                            "Local consensus stage evidence is not settlement proof",
                        ],
                        "claim_boundaries_total": 1,
                        "claim_boundaries_limit": 8,
                        "claim_boundaries_truncated": False,
                        "redacted": True,
                    },
                    "request_evidence": {
                        "present": True,
                        "action": "consensus_start",
                        "idempotency_key_present": False,
                    },
                    "upstream_evidence": {
                        "present": True,
                        "event_ids_count": 1,
                        "claim_gate_summary": {
                            "present": True,
                            "surface": "integration_spine.reward_context",
                            "local_actuator_execution_claim_allowed": True,
                            "external_settlement_finality_claim_allowed": False,
                            "production_readiness_claim_allowed": False,
                            "blocked_claim_ids": ["settlement_finality"],
                            "payloads_redacted": True,
                        },
                        "cross_plane_claim_gate_summary": {
                            "present": True,
                            "surface": "integration_spine.reward_context",
                            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
                            "allowed": False,
                            "requested_claim_ids": ["settlement_finality"],
                            "blockers": [
                                "integration_spine_local_contract_only",
                            ],
                            "payloads_redacted": True,
                        },
                        "upstream_claim_boundary_present": True,
                        "payloads_redacted": True,
                    },
                },
                "claim_boundary_summary": {
                    "present": True,
                    "claim_boundaries": [
                        "Local consensus stage evidence is not settlement proof",
                    ],
                    "claim_boundaries_total": 1,
                    "claim_boundaries_limit": 8,
                    "claim_boundaries_truncated": False,
                    "redacted": True,
                },
                "upstream_claim_gate_summary": {
                    "present": True,
                    "surface": "integration_spine.reward_context",
                    "local_actuator_execution_claim_allowed": True,
                    "external_settlement_finality_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "blocked_claim_ids": ["settlement_finality"],
                    "payloads_redacted": True,
                },
                "upstream_cross_plane_claim_gate_summary": {
                    "present": True,
                    "surface": "integration_spine.reward_context",
                    "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
                    "allowed": False,
                    "requested_claim_ids": ["settlement_finality"],
                    "blockers": ["integration_spine_local_contract_only"],
                    "payloads_redacted": True,
                },
                "cross_plane_evidence_profile": {
                    "primary_status": "local_only",
                    "dataplane_confirmed": False,
                    "trust_confirmed": False,
                    "settlement_confirmed": False,
                    "production_ready_candidate": False,
                },
                "economy_finality_summary": {
                    "present": True,
                    "local_or_pending_only": True,
                    "settlement_confirmed": False,
                    "dataplane_confirmed": False,
                    "production_ready_candidate": False,
                },
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
    assert citation["evidence_summary"]["available"] is True
    assert citation["evidence_summary"]["request_evidence"]["present"] is True
    assert citation["evidence_summary"]["upstream_evidence"]["event_ids_count"] == 1
    assert citation["upstream_claim_gate_summary"]["surface"] == (
        "integration_spine.reward_context"
    )
    assert (
        citation["upstream_claim_gate_summary"][
            "external_settlement_finality_claim_allowed"
        ]
        is False
    )
    assert citation["upstream_cross_plane_claim_gate_summary"]["allowed"] is False
    assert citation["claim_boundary_summary"] == {
        "present": True,
        "claim_boundaries": [
            "Local consensus stage evidence is not settlement proof",
        ],
        "claim_boundaries_total": 1,
        "claim_boundaries_limit": 8,
        "claim_boundaries_truncated": False,
        "redacted": True,
    }
    assert citation["cross_plane_evidence_profile"]["primary_status"] == "local_only"
    assert citation["cross_plane_evidence_profile"]["dataplane_confirmed"] is False
    assert citation["economy_finality_summary"]["local_or_pending_only"] is True
    assert citation["economy_finality_summary"]["settlement_confirmed"] is False
    assert citation["redacted"] is True
