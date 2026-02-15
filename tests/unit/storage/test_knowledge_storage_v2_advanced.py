import pytest


def _patch_crdt_sync(monkeypatch):
    import sys
    import types

    class _DummyCRDTSync:
        def __init__(self, *args, **kwargs):
            pass

        async def sync(self, *args, **kwargs):
            return None

    dummy_module = types.ModuleType("src.data_sync.crdt_sync")
    dummy_module.CRDTSync = _DummyCRDTSync
    if "src.data_sync" not in sys.modules:
        sys.modules["src.data_sync"] = types.ModuleType("src.data_sync")
    monkeypatch.setitem(sys.modules, "src.data_sync.crdt_sync", dummy_module)


def test_prepare_text_for_embedding_includes_result_and_duration(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")
    _patch_crdt_sync(monkeypatch)

    # Stub VectorIndex
    class _StubVectorIndex:
        def __init__(self, *args, **kwargs):
            pass

        def load(self, *args, **kwargs):
            return None

        def embed(self, text):
            return [0.0]

        def add(self, *args, **kwargs):
            return 0

        def search(self, *args, **kwargs):
            return []

        def get_stats(self):
            return {}

    monkeypatch.setattr(
        "src.storage.knowledge_storage_v2.VectorIndex", _StubVectorIndex
    )

    from src.storage.knowledge_storage_v2 import (IncidentEntry,
                                                  KnowledgeStorageV2)

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    entry = IncidentEntry(
        incident_id="i",
        timestamp=1.0,
        node_id="n",
        anomaly_type="CPU",
        metrics={},
        root_cause="rc",
        recovery_plan="plan",
        execution_result={"success": True, "duration": 1.2},
    )

    text = ks._prepare_text_for_embedding(entry)
    assert "Anomaly type: CPU" in text
    assert "Root cause: rc" in text
    assert "Recovery plan: plan" in text
    assert "Result: True" in text
    assert "Duration: 1.2s" in text


@pytest.mark.asyncio
async def test_search_incidents_sorts_and_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")
    _patch_crdt_sync(monkeypatch)

    # Stub VectorIndex with deterministic vector results
    class _StubVectorIndex:
        def __init__(self, *args, **kwargs):
            pass

        def load(self, *args, **kwargs):
            return None

        def embed(self, text):
            return [0.0]

        def add(self, *args, **kwargs):
            return 0

        def search(self, *args, **kwargs):
            return [
                (1, 0.8, {"incident_id": "i1"}),
                (2, 0.95, {"incident_id": "i2"}),
                (3, 0.7, {"incident_id": "i3"}),
            ]

        def get_stats(self):
            return {"total_documents": 3}

    monkeypatch.setattr(
        "src.storage.knowledge_storage_v2.VectorIndex", _StubVectorIndex
    )

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    # Patch DB fetch to return minimal dict
    def _get(incident_id):
        return {"incident_id": incident_id}

    monkeypatch.setattr(ks, "_get_incident_from_db", _get)

    res = await ks.search_incidents("q", k=2, threshold=0.0)
    assert [r["incident_id"] for r in res] == ["i2", "i1"]
    assert res[0]["similarity"] >= res[1]["similarity"]


def test_get_stats_success(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")
    _patch_crdt_sync(monkeypatch)

    class _StubVectorIndex:
        def __init__(self, *args, **kwargs):
            pass

        def load(self, *args, **kwargs):
            return None

        def get_stats(self):
            return {"total_documents": 0}

        def embed(self, text):
            return [0.0]

        def add(self, *args, **kwargs):
            return 0

        def search(self, *args, **kwargs):
            return []

    monkeypatch.setattr(
        "src.storage.knowledge_storage_v2.VectorIndex", _StubVectorIndex
    )

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    # Insert 1 incident row for count
    import sqlite3

    conn = sqlite3.connect(ks.db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO incidents (incident_id, timestamp, node_id, anomaly_type, metrics, root_cause, recovery_plan, execution_result, signature, ipfs_cid, embedding) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("i", 1.0, "n", "A", "{}", "rc", "p", "{}", None, None, None),
    )
    conn.commit()
    conn.close()

    stats = ks.get_stats()
    assert stats["total_incidents"] == 1
    assert stats["ipfs_available"] is True
    assert "vector_index_stats" in stats
