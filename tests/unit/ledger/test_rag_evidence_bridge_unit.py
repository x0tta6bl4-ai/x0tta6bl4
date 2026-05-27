from __future__ import annotations

from pathlib import Path

import pytest

from src.ledger.rag_search import LedgerRAGSearch


class _FakeRAG:
    def __init__(self):
        self.documents = []

    def add_document(self, text: str, document_id: str, metadata: dict):
        self.documents.append(
            {"text": text, "document_id": document_id, "metadata": metadata}
        )
        return [f"{document_id}:chunk"]


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
    assert status["indexed"] is False


@pytest.mark.asyncio
async def test_index_verification_evidence_adds_docs_with_metadata(tmp_path):
    verification_root = tmp_path / "docs" / "verification"
    _write(verification_root / "GHOST_PULSE_PROOF_GATE_LATEST.md", "# proof")
    _write(verification_root / "ghost-pulse-proof-gate-1" / "proof.json", '{"status":"ok"}')

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
    assert "document_id" in ledger.rag.documents[0]


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
    metadata = document["metadata"]
    assert metadata["source"] == "EventBus"
    assert metadata["source_class"] == "event_trace"
    assert metadata["relative_path"] == ".agent_coordination/events.log"
    assert metadata["event_id"] == "event-1"
    assert metadata["source_agent"] == "swarm-pbft"
    assert metadata["layer"] == "swarm_consensus_to_control_plane"
    assert metadata["entrypoint"] == "src/swarm/pbft.py"
    assert metadata["redacted"] is True


@pytest.mark.asyncio
async def test_index_event_traces_maps_source_agent_alias_to_registered_service(tmp_path):
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
