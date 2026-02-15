import os

import numpy as np

from src.storage.vector_index import VectorIndex


def test_vector_index_embed_fallback_has_correct_shape(monkeypatch):
    # Force no embedding model
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=8)

    # Make fallback deterministic
    monkeypatch.setattr(np.random, "rand", lambda n: np.ones(n, dtype=float))

    emb = vi.embed("hello")
    assert isinstance(emb, np.ndarray)
    assert emb.shape == (8,)


def test_vector_index_add_and_search_without_hnsw(monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=4)

    doc_id = vi.add(
        "doc",
        metadata={"anomaly_type": "A", "root_cause": "R", "action_taken": "X"},
        embedding=np.array([1, 0, 0, 0], dtype=np.float32),
    )
    assert doc_id == 0
    assert vi.metadata[0]["text"] == "doc"

    # With no HNSW index initialized, search should return empty
    assert vi.search("q") == []


def test_vector_index_save_and_load_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=4, index_path=tmp_path)
    vi.add(
        "doc",
        metadata={"anomaly_type": "A"},
        embedding=np.array([1, 0, 0, 0], dtype=np.float32),
    )

    vi.save(tmp_path)

    vi2 = VectorIndex(dimension=4, index_path=tmp_path)
    vi2.load(tmp_path)

    assert vi2.next_id == 1
    assert "0" in vi2.metadata or 0 in vi2.metadata

    # Metadata keys may roundtrip through JSON as strings
    meta = vi2.metadata.get(0) or vi2.metadata.get("0")
    assert meta["text"] == "doc"
