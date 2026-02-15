import json
from types import SimpleNamespace

import numpy as np

from src.storage.vector_index import VectorIndex


def test_vector_index_prepare_text_includes_metadata(monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=4)
    out = vi._prepare_text(
        "base",
        {"anomaly_type": "CPU", "root_cause": "load", "action_taken": "restart"},
    )
    assert "base" in out
    assert "Type: CPU" in out
    assert "Root cause: load" in out
    assert "Action: restart" in out


def test_vector_index_embed_uses_model_encode(monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=3)

    model = SimpleNamespace()
    model.encode = lambda text, convert_to_numpy=True: np.array(
        [1.0, 2.0, 3.0], dtype=np.float32
    )
    vi.embedding_model = model

    emb = vi.embed("x")
    assert emb.tolist() == [1.0, 2.0, 3.0]


def test_vector_index_add_and_search_with_mock_hnsw(monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=2)

    # Force HNSW path without real hnswlib
    monkeypatch.setattr("src.storage.vector_index.HNSW_AVAILABLE", True)

    class _MockIndex:
        def __init__(self):
            self.added = []

        def add_items(self, vectors, ids):
            self.added.append((vectors.shape, list(ids)))

        def knn_query(self, vector, k=10):
            # One result with cosine distance 0.1 -> similarity 0.9
            return np.array([[0]]), np.array([[0.1]])

    vi.index = _MockIndex()

    doc_id = vi.add(
        "doc",
        metadata={"incident_id": "i1"},
        embedding=np.array([1.0, 0.0], dtype=np.float32),
    )
    assert doc_id == 0
    assert vi.index.added

    results = vi.search("q", k=5, threshold=0.8)
    assert results
    rid, score, meta = results[0]
    assert rid == 0
    assert score >= 0.8
    assert meta["incident_id"] == "i1"


def test_vector_index_load_without_metadata_file(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=4, index_path=tmp_path)
    # Should not raise
    vi.load(tmp_path)


def test_vector_index_get_stats_keys(monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=4)
    stats = vi.get_stats()
    assert "total_documents" in stats
    assert "dimension" in stats
    assert "hnsw_available" in stats
    assert "embedding_model_available" in stats
