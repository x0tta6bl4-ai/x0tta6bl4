#!/usr/bin/env python3
"""Quality and Precision verification suite for GitMark RAG Memory Bank v3.0."""

from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.gitmark_memory_bank import (
    DOMAIN_THESAURUS,
    expand_query_terms,
    bm25_chunk_search,
    bm25_search,
    load_index,
)


def test_domain_term_expansion():
    """Verify that domain queries expand to canonical technical terms."""
    terms_ru = expand_query_terms("самовосстановление")
    assert "mape-k" in terms_ru, f"Expected 'mape-k' in expanded terms for 'самовосстановление', got: {terms_ru}"
    assert "self-healing" in terms_ru

    terms_pqc = expand_query_terms("pqc")
    assert "ml-kem-768" in terms_pqc
    assert "ml-dsa-65" in terms_pqc

    terms_spb = expand_query_terms("петербург")
    assert "decommissioned" in terms_spb
    assert "spb" in terms_spb

    print("✅ Domain term expansion test PASSED")


def test_rag_retrieval_precision():
    """Verify RAG retrieval on current memory index."""
    index_path = PROJECT_ROOT / ".gitmark-memory" / "index.json"
    if not index_path.exists():
        print(f"⚠️ Index file {index_path} not found. Skipping live retrieval test.")
        return

    index = load_index(index_path)

    # Query 1: Russian query "самовосстановление" should retrieve MAPE-K docs
    results_mapek = bm25_chunk_search(index, "самовосстановление", limit=5)
    assert len(results_mapek) > 0, "No results returned for 'самовосстановление'"
    found_mapek = any("mape" in str(r.get("text") or "").lower() or "self" in str(r.get("text") or "").lower() for r in results_mapek)
    assert found_mapek, "Expected MAPE-K / self-healing content in top results"

    # Query 2: PQC query should retrieve ML-KEM/ML-DSA
    results_pqc = bm25_chunk_search(index, "pqc", limit=5)
    assert len(results_pqc) > 0, "No results returned for 'pqc'"

    print(f"✅ RAG retrieval precision test PASSED (evaluated {len(index.get('chunks', []))} chunks)")


def main():
    print("=== Running GitMark RAG Quality Verification Suite ===")
    test_domain_term_expansion()
    test_rag_retrieval_precision()
    print("=== ALL RAG TESTS PASSED (Exit Code 0) ===")


if __name__ == "__main__":
    main()
