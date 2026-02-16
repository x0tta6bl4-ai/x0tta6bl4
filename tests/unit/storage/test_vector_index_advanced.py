import json

import numpy as np

from src.storage.vector_index import VectorIndex


def test_vector_index_save_handles_metadata_write_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    vi = VectorIndex(dimension=4, index_path=tmp_path)
    vi.add(
        "doc",
        metadata={"anomaly_type": "A"},
        embedding=np.array([1, 0, 0, 0], dtype=np.float32),
    )

    def _boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", _boom)

    # save() catches exceptions and should not raise
    vi.save(tmp_path)


def test_vector_index_load_handles_invalid_metadata_json(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    (tmp_path / "metadata.json").write_text("{not json")

    vi = VectorIndex(dimension=4, index_path=tmp_path)

    # load() catches exceptions and should not raise
    vi.load(tmp_path)


def test_vector_index_load_hnsw_load_index_failure_sets_index_none(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.delenv("RAG_DISABLE_HNSW", raising=False)

    # Create metadata + dummy index file to exercise HNSW load branch
    (tmp_path / "metadata.json").write_text(
        json.dumps({"metadata": {}, "next_id": 0, "dimension": 4})
    )
    (tmp_path / "hnsw_index.bin").write_bytes(b"x")

    monkeypatch.setattr("src.storage.vector_index.HNSW_AVAILABLE", True)

    vi = VectorIndex(dimension=4, index_path=tmp_path)

    class _Idx:
        def load_index(self, *args, **kwargs):
            raise RuntimeError("bad index")

        def set_ef(self, *args, **kwargs):
            return None

    def _init_index():
        vi.index = _Idx()

    monkeypatch.setattr(vi, "_init_index", _init_index)

    vi.load(tmp_path)
    assert vi.index is None
