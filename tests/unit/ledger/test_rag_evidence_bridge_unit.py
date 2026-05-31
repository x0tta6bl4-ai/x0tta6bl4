from __future__ import annotations

from pathlib import Path

import pytest

from src.coordination.events import EventBus, EventType
from src.ledger.rag_search import LedgerRAGSearch
from src.network import yggdrasil_client
from src.services.service_event_trace import service_event_trace_history


class _FakeRAG:
    def __init__(self):
        self.documents = []

    def add_document(self, text: str, document_id: str, metadata: dict):
        self.documents.append(
            {"text": text, "document_id": document_id, "metadata": metadata}
        )
        return [f"{document_id}:chunk"]


class _Chunk:
    def __init__(self, text: str, metadata: dict):
        self.text = text
        self.metadata = metadata


class _RAGResult:
    def __init__(self, chunks: list[_Chunk], scores: list[float]):
        self.retrieved_chunks = chunks
        self.scores = scores
        self.retrieval_time_ms = 1.0
        self.rerank_time_ms = 0.0


class _RetrieveRAG:
    def __init__(self, chunks: list[_Chunk], scores: list[float]):
        self._result = _RAGResult(chunks, scores)

    def retrieve(self, _question: str, top_k: int):
        return self._result


class _Completed:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_verification_evidence_status_counts_text_artifacts(tmp_path):
    verification_root = tmp_path / "docs" / "verification"
    _write(verification_root / "GHOST_PULSE_LOCAL_EVIDENCE_LATEST.md", "# latest")
    _write(verification_root / "run-1" / "evidence.json", '{"ok": true}')
    _write(verification_root / "run-1" / "events.jsonl", '{"event": 1}\n')
    _write(verification_root / "run-1" / "capture.pcap", "not indexed")

    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=verification_root,
        enable_reranking=False,
    )

    status = ledger.verification_evidence_status()

    assert status["root_exists"] is True
    assert status["indexable_files"] == 3
    assert status["by_suffix"] == {".json": 1, ".jsonl": 1, ".md": 1}
    assert status["latest_alias_count"] == 1
    assert status["claim_status_counts"] == {
        "latest_verification_alias": 1,
        "verification_artifact": 2,
    }
    assert status["indexed"] is False


@pytest.mark.asyncio
async def test_index_verification_evidence_adds_docs_with_metadata(tmp_path):
    verification_root = tmp_path / "docs" / "verification"
    _write(verification_root / "GHOST_PULSE_PROOF_GATE_LATEST.md", "# proof")
    _write(
        verification_root / "ghost-pulse-proof-gate-1" / "proof.json", '{"status":"ok"}'
    )

    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=verification_root,
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    success = await ledger.index_verification_evidence()

    assert success is True
    assert ledger.is_verification_indexed() is True
    assert ledger.verification_evidence_status()["indexed_files"] == 2
    assert ledger.verification_evidence_status()["indexed_chunks"] == 2
    assert len(ledger.rag.documents) == 2
    metadata = ledger.rag.documents[0]["metadata"]
    assert metadata["source"] == "docs/verification"
    assert metadata["source_class"] == "verification_evidence"
    assert metadata["relative_path"].startswith("docs/verification/")
    assert metadata["claim_status"] in {
        "latest_verification_alias",
        "verification_artifact",
    }
    assert metadata["claim_scope"] == "verification_artifact_not_automatic_truth"
    assert metadata["historical_claim_inventory"] is False
    assert "document_id" in ledger.rag.documents[0]


@pytest.mark.asyncio
async def test_index_verification_evidence_marks_external_dpi_gap_record(tmp_path):
    verification_root = tmp_path / "docs" / "verification"
    _write(
        verification_root / "incoming" / "dpi_lab.json",
        """
{
  "claim_id": "dpi_lab",
  "mode": "EXTERNAL_EVIDENCE_GAP_RECORD",
  "status": "INCOMPLETE",
  "gap_artifact_role": "evidence_gap_record",
  "failures": ["missing external input: authorized lab identity and scope"],
  "missing_inputs": ["authorized lab identity and scope"]
}
""",
    )

    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=verification_root,
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    status_before = ledger.verification_evidence_status()
    success = await ledger.index_verification_evidence()
    status_after = ledger.verification_evidence_status()

    assert success is True
    assert status_before["claim_status_counts"] == {"external_dpi_gap_record": 1}
    assert status_before["external_dpi_gap_record_count"] == 1
    assert status_after["indexed_files"] == 1
    metadata = ledger.rag.documents[0]["metadata"]
    assert metadata["source"] == "docs/verification"
    assert metadata["source_class"] == "external_dpi_gap_record"
    assert metadata["relative_path"] == "docs/verification/incoming/dpi_lab.json"
    assert metadata["claim_status"] == "external_dpi_gap_record"
    assert metadata["claim_scope"] == "external_dpi_gap_record_not_proof"
    assert metadata["current_evidence"] is False
    assert metadata["requires_current_evidence_context"] is True
    assert metadata["external_evidence_gap_record"] is True
    assert metadata["runtime_memory_priority"] == 10
    gate = metadata["external_dpi_intake_claim_gate_summary"]
    assert gate["schema"] == (
        "x0tta6bl4.external_dpi_intake.ledger_citation_claim_gate.v1"
    )
    assert gate["external_evidence_gap_record"] is True
    assert gate["candidate_file_observed_claim_allowed"] is True
    assert gate["bounded_external_dpi_candidate_ready_to_import_claim_allowed"] is False
    assert gate["proof_gate_dpi_bypass_claim_allowed"] is False
    assert gate["production_readiness_claim_allowed"] is False
    assert gate["this_citation_is_proof"] is False
    assert gate["blockers"] == [
        "external_evidence_gap_record_not_proof",
        "external_dpi_candidate_not_verified",
        "external_dpi_candidate_has_failures",
        "external_dpi_candidate_missing_inputs",
    ]


@pytest.mark.asyncio
async def test_index_verification_evidence_can_limit_files(tmp_path):
    verification_root = tmp_path / "docs" / "verification"
    _write(verification_root / "a.md", "a")
    _write(verification_root / "b.md", "b")

    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=verification_root,
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    success = await ledger.index_verification_evidence(max_files=1)

    assert success is True
    assert ledger.verification_evidence_status()["indexed_files"] == 1
    assert len(ledger.rag.documents) == 1


@pytest.mark.asyncio
async def test_index_evidence_marks_current_and_historical_architecture_docs(tmp_path):
    docs_root = tmp_path / "docs"
    _write(
        docs_root / "architecture" / "CURRENT_CROSS_PLANE_EVIDENCE_MAP.json",
        '{"status":"working_map_not_production_completion_proof"}',
    )
    _write(
        docs_root / "architecture" / "CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
        "# Current Active Goal Gap Audit",
    )
    _write(
        docs_root / "01-architecture" / "master-system.md",
        "# historical production-ready claim inventory",
    )
    _write(
        docs_root / "05-operations" / "project-completion-report-v1.5.md",
        "# historical operational production-ready claim inventory",
    )

    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=docs_root,
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    success = await ledger.index_verification_evidence()

    assert success is True
    metadata_by_path = {
        document["metadata"]["relative_path"]: document["metadata"]
        for document in ledger.rag.documents
    }
    current_map = metadata_by_path[
        "docs/architecture/CURRENT_CROSS_PLANE_EVIDENCE_MAP.json"
    ]
    active_audit = metadata_by_path[
        "docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"
    ]
    historical = metadata_by_path["docs/01-architecture/master-system.md"]
    historical_ops = metadata_by_path[
        "docs/05-operations/project-completion-report-v1.5.md"
    ]

    assert current_map["source"] == "docs/architecture"
    assert current_map["claim_status"] == "current_evidence_map"
    assert current_map["current_evidence"] is True
    assert current_map["requires_current_evidence_context"] is False
    assert active_audit["claim_status"] == "current_active_audit"
    assert active_audit["runtime_memory_priority"] > current_map["runtime_memory_priority"]
    assert historical["source"] == "docs/01-architecture"
    assert historical["claim_status"] == "historical_claim_inventory"
    assert historical["historical_claim_inventory"] is True
    assert historical["requires_current_evidence_context"] is True
    assert historical["current_evidence"] is False
    assert historical_ops["source"] == "docs/05-operations"
    assert historical_ops["source_class"] == "historical_operations_claim_inventory"
    assert historical_ops["claim_status"] == "historical_claim_inventory"
    assert historical_ops["historical_claim_inventory"] is True
    assert historical_ops["requires_current_evidence_context"] is True
    assert historical_ops["current_evidence"] is False
    assert current_map["runtime_memory_priority"] > historical["runtime_memory_priority"]
    assert current_map["runtime_memory_priority"] > historical_ops["runtime_memory_priority"]


@pytest.mark.asyncio
async def test_index_current_evidence_indexes_only_current_architecture_files(tmp_path):
    architecture_root = tmp_path / "docs" / "architecture"
    _write(
        architecture_root / "CURRENT_ACTIVE_GOAL_GAP_AUDIT.md",
        "# Current Active Goal Gap Audit",
    )
    _write(
        architecture_root / "CURRENT_POLICY_ENFORCEMENT_MAP.json",
        '{"status":"working_map"}',
    )
    _write(architecture_root / "overview.md", "# architecture context")

    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        current_evidence_root=architecture_root,
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    status_before = ledger.current_evidence_status()
    success = await ledger.index_current_evidence()
    status_after = ledger.current_evidence_status()

    assert status_before["indexable_files"] == 2
    assert status_before["claim_status_counts"] == {
        "current_active_audit": 1,
        "current_evidence_map": 1,
    }
    assert success is True
    assert ledger.is_current_evidence_indexed() is True
    assert status_after["indexed"] is True
    assert status_after["indexed_files"] == 2
    assert len(ledger.rag.documents) == 2
    metadata_by_path = {
        document["metadata"]["relative_path"]: document["metadata"]
        for document in ledger.rag.documents
    }
    assert "docs/architecture/overview.md" not in metadata_by_path
    assert (
        metadata_by_path["docs/architecture/CURRENT_ACTIVE_GOAL_GAP_AUDIT.md"][
            "claim_status"
        ]
        == "current_active_audit"
    )
    assert (
        metadata_by_path["docs/architecture/CURRENT_POLICY_ENFORCEMENT_MAP.json"][
            "claim_status"
        ]
        == "current_evidence_map"
    )


@pytest.mark.asyncio
async def test_query_soft_ranks_current_evidence_above_historical_claims(tmp_path):
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger._indexed = True
    ledger.rag = _RetrieveRAG(
        [
            _Chunk(
                "historical production ready claim",
                {
                    "title": "master-system",
                    "claim_status": "historical_claim_inventory",
                    "historical_claim_inventory": True,
                    "runtime_memory_priority": 20,
                },
            ),
            _Chunk(
                "current active evidence map",
                {
                    "title": "CURRENT_CROSS_PLANE_EVIDENCE_MAP",
                    "claim_status": "current_evidence_map",
                    "current_evidence": True,
                    "runtime_memory_priority": 95,
                },
            ),
        ],
        [0.50, 0.48],
    )

    result = await ledger.query("current production readiness evidence")

    assert result.results[0]["metadata"]["claim_status"] == "current_evidence_map"
    assert result.results[0]["score"] == 0.48
    assert result.results[0]["claim_adjusted_score"] > (
        result.results[1]["claim_adjusted_score"]
    )
    assert result.results[1]["metadata"]["claim_status"] == (
        "historical_claim_inventory"
    )


@pytest.mark.asyncio
async def test_query_soft_ranks_current_evidence_above_external_dpi_gap_record(
    tmp_path,
):
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger._indexed = True
    ledger.rag = _RetrieveRAG(
        [
            _Chunk(
                "incoming dpi gap record",
                {
                    "title": "dpi_lab",
                    "claim_status": "external_dpi_gap_record",
                    "external_evidence_gap_record": True,
                    "current_evidence": False,
                    "requires_current_evidence_context": True,
                    "runtime_memory_priority": 10,
                },
            ),
            _Chunk(
                "current cross-plane evidence map",
                {
                    "title": "CURRENT_CROSS_PLANE_EVIDENCE_MAP",
                    "claim_status": "current_evidence_map",
                    "current_evidence": True,
                    "runtime_memory_priority": 95,
                },
            ),
        ],
        [0.50, 0.48],
    )

    result = await ledger.query("external dpi bypass current evidence")

    assert result.results[0]["metadata"]["claim_status"] == "current_evidence_map"
    assert result.results[1]["metadata"]["claim_status"] == "external_dpi_gap_record"
    assert result.results[1]["claim_adjusted_score"] < result.results[1]["score"]


@pytest.mark.asyncio
async def test_query_preserves_event_trace_claim_boundary_summary(tmp_path):
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger._indexed = True
    ledger.rag = _RetrieveRAG(
        [
            _Chunk(
                "redacted event trace",
                {
                    "title": "EventBus pipeline.stage_end",
                    "source_class": "event_trace",
                    "claim_boundary_summary": {
                        "present": True,
                        "claim_boundaries": ["Local observation only"],
                        "claim_boundaries_total": 1,
                        "claim_boundaries_limit": 8,
                        "claim_boundaries_truncated": False,
                        "redacted": True,
                    },
                },
            ),
        ],
        [0.42],
    )

    result = await ledger.query("local observed-state event boundary")

    metadata = result.results[0]["metadata"]
    assert metadata["source_class"] == "event_trace"
    assert metadata["claim_boundary_summary"]["present"] is True
    assert metadata["claim_boundary_summary"]["claim_boundaries"] == [
        "Local observation only",
    ]


@pytest.mark.asyncio
async def test_index_event_traces_adds_redacted_docs_with_citation_metadata(tmp_path):
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    success = await ledger.index_event_traces(
        {
            "redacted": True,
            "filter": {
                "service_name": "swarm-pbft",
                "layer": "swarm_consensus_to_control_plane",
                "services": [
                    {
                        "service_name": "swarm-pbft",
                        "layer": "swarm_consensus_to_control_plane",
                        "entrypoint": "src/swarm/pbft.py",
                    }
                ],
            },
            "events": [
                {
                    "event_id": "event-1",
                    "event_type": "pipeline.stage_start",
                    "source_agent": "swarm-pbft",
                    "timestamp": "2026-05-27T00:00:00",
                    "target_agents": None,
                    "data": {"spiffe_id": "[redacted]", "stage": "consensus"},
                    "evidence_summary": {
                        "available": True,
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
                        "cross_plane_evidence_profile": {
                            "primary_status": "local_only",
                            "planes_observed": ["evidence_plane"],
                            "local_only": True,
                            "dataplane_confirmed": False,
                            "trust_confirmed": False,
                            "settlement_confirmed": False,
                            "production_ready_candidate": False,
                        },
                        "economy_finality_summary": {
                            "present": True,
                            "local_or_pending_only": True,
                            "submitted_transaction_only": False,
                            "payment_provider_settlement_confirmed": False,
                            "bank_settlement_confirmed": False,
                            "token_settlement_finality_confirmed": False,
                            "settlement_confirmed": False,
                            "dataplane_confirmed": False,
                            "production_ready_candidate": False,
                        },
                    },
                    "redacted": True,
                }
            ],
        }
    )

    assert success is True
    assert ledger.is_event_trace_indexed() is True
    assert ledger.event_trace_status()["indexed_events"] == 1
    assert len(ledger.rag.documents) == 1
    document = ledger.rag.documents[0]
    assert "spiffe://secret" not in document["text"]
    assert '"evidence_summary"' in document["text"]
    assert '"event_ids_count": 1' in document["text"]
    assert '"upstream_claim_gate_summary"' in document["text"]
    assert '"economy_finality_summary"' in document["text"]
    assert '"claim_boundary_summary"' in document["text"]
    metadata = document["metadata"]
    assert metadata["source"] == "EventBus"
    assert metadata["source_class"] == "event_trace"
    assert metadata["relative_path"] == ".agent_coordination/events.log"
    assert metadata["event_id"] == "event-1"
    assert metadata["source_agent"] == "swarm-pbft"
    assert metadata["layer"] == "swarm_consensus_to_control_plane"
    assert metadata["entrypoint"] == "src/swarm/pbft.py"
    assert metadata["evidence_summary"]["available"] is True
    assert metadata["evidence_summary"]["request_evidence"]["present"] is True
    assert metadata["evidence_summary"]["upstream_evidence"]["event_ids_count"] == 1
    assert metadata["upstream_claim_gate_summary"]["surface"] == (
        "integration_spine.reward_context"
    )
    assert (
        metadata["upstream_claim_gate_summary"][
            "external_settlement_finality_claim_allowed"
        ]
        is False
    )
    assert metadata["upstream_cross_plane_claim_gate_summary"]["allowed"] is False
    assert metadata["cross_plane_evidence_profile"]["primary_status"] == "local_only"
    assert metadata["cross_plane_evidence_profile"]["dataplane_confirmed"] is False
    assert metadata["economy_finality_summary"]["local_or_pending_only"] is True
    assert metadata["economy_finality_summary"][
        "payment_provider_settlement_confirmed"
    ] is False
    assert metadata["claim_boundary_summary"] == {
        "present": True,
        "claim_boundaries": [
            "Local consensus stage evidence is not settlement proof",
        ],
        "claim_boundaries_total": 1,
        "claim_boundaries_limit": 8,
        "claim_boundaries_truncated": False,
        "redacted": True,
    }
    assert metadata["redacted"] is True


@pytest.mark.asyncio
async def test_index_event_traces_maps_source_agent_alias_to_registered_service(
    tmp_path,
):
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    success = await ledger.index_event_traces(
        {
            "redacted": True,
            "filter": {
                "service_name": "pqc-zero-trust-executor",
                "layer": "self_healing_pqc_identity",
                "services": [
                    {
                        "service_name": "pqc-zero-trust-executor",
                        "source_agent": "pqc-zero-trust-healer",
                        "layer": "self_healing_pqc_identity",
                        "entrypoint": "src/self_healing/pqc_zero_trust_healer.py",
                    }
                ],
            },
            "events": [
                {
                    "event_id": "event-pqc-healer-1",
                    "event_type": "pipeline.stage_end",
                    "source_agent": "pqc-zero-trust-healer",
                    "timestamp": "2026-05-27T00:00:00",
                    "target_agents": None,
                    "data": {"spiffe_id": "[redacted]", "stage": "action_completed"},
                    "redacted": True,
                }
            ],
        }
    )

    assert success is True
    metadata = ledger.rag.documents[0]["metadata"]
    assert metadata["source_agent"] == "pqc-zero-trust-healer"
    assert metadata["service_name"] == "pqc-zero-trust-executor"
    assert metadata["layer"] == "self_healing_pqc_identity"
    assert metadata["entrypoint"] == "src/self_healing/pqc_zero_trust_healer.py"


@pytest.mark.asyncio
async def test_yggdrasil_observed_state_event_is_ledger_indexable(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    monkeypatch.setattr(
        yggdrasil_client,
        "_find_yggdrasilctl",
        lambda: "/usr/local/bin/yggdrasilctl",
    )
    monkeypatch.setattr(
        yggdrasil_client.subprocess,
        "run",
        lambda *_a, **_k: _Completed(
            "Peer  Port  Protocol  Remote Address\n1  tcp  10.0.0.1\n"
        ),
    )

    peers = yggdrasil_client.get_yggdrasil_peers(event_bus=bus)
    trace_payload = service_event_trace_history(
        bus,
        service_name="yggdrasil-client",
        event_type=EventType.PIPELINE_STAGE_END,
        limit=10,
    )
    trace_text = str(trace_payload)

    assert peers["count"] == 1
    assert trace_payload["events_total"] == 1
    assert trace_payload["filter"]["services"][0]["layer"] == (
        "network_yggdrasil_observed_state"
    )
    assert "10.0.0.1" not in trace_text

    success = await ledger.index_event_traces(trace_payload)

    assert success is True
    assert len(ledger.rag.documents) == 1
    document = ledger.rag.documents[0]
    assert "10.0.0.1" not in document["text"]
    assert document["metadata"]["source"] == "EventBus"
    assert document["metadata"]["source_class"] == "event_trace"
    assert document["metadata"]["source_agent"] == "yggdrasil-client"
    assert document["metadata"]["service_name"] == "yggdrasil-client"
    assert document["metadata"]["layer"] == "network_yggdrasil_observed_state"
    assert document["metadata"]["entrypoint"] == "src/network/yggdrasil_client.py"
    assert document["metadata"]["cross_plane_evidence_profile"]["primary_status"] == (
        "local_only"
    )
    assert document["metadata"]["cross_plane_evidence_profile"][
        "dataplane_confirmed"
    ] is False
    claim_boundary_summary = document["metadata"]["claim_boundary_summary"]
    assert claim_boundary_summary["present"] is True
    assert claim_boundary_summary["redacted"] is True
    assert claim_boundary_summary["claim_boundaries_total"] == 1
    assert claim_boundary_summary["claim_boundaries_truncated"] is False
    assert "Read-only local yggdrasilctl observation" in (
        claim_boundary_summary["claim_boundaries"][0]
    )
    assert "10.0.0.1" not in str(claim_boundary_summary)
    assert document["metadata"]["redacted"] is True


@pytest.mark.asyncio
async def test_index_event_traces_rejects_unredacted_payload(tmp_path):
    ledger = LedgerRAGSearch(
        continuity_file=tmp_path / "CONTINUITY.md",
        verification_root=tmp_path / "docs" / "verification",
        enable_reranking=False,
    )
    ledger.rag = _FakeRAG()

    success = await ledger.index_event_traces(
        {
            "redacted": False,
            "events": [
                {
                    "event_id": "event-1",
                    "data": {"spiffe_id": "spiffe://secret"},
                }
            ],
        }
    )

    assert success is False
    assert ledger.rag.documents == []
